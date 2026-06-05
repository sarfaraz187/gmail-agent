"""
Webhook endpoints for Gmail push notifications via Pub/Sub.

These endpoints handle:
- POST /webhook/gmail: Receives Pub/Sub push notifications from Gmail
- POST /renew-watch: Renews Gmail watch (called by Cloud Scheduler)
- GET /watch-status: Check current watch status

Security:
- Pub/Sub push authentication via JWT verification
- Rate limiting via slowapi (configured in main.py)
"""

import base64
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from email_agent.agent import create_initial_state, invoke_graph
from email_agent.api.schemas import (
    GmailNotificationData,
    PubSubPushRequest,
    RenewWatchResponse,
    WatchStatusResponse,
    WebhookAckResponse,
)
from email_agent.config import settings
from email_agent.gmail import gmail_client, label_manager, watch_service
from email_agent.gmail.client import StaleHistoryError
from email_agent.security.pubsub_auth import (
    PubSubAuthError,
    is_pubsub_auth_enabled,
    verify_pubsub_token,
)
from email_agent.security.sanitization import redact_sensitive_for_logging
from email_agent.storage import history_tracker

logger = logging.getLogger(__name__)

# Create router for webhook endpoints
webhook_router = APIRouter(tags=["webhook"])

# Rate limiter for webhook endpoints
limiter = Limiter(key_func=get_remote_address)


@webhook_router.post("/webhook/gmail", response_model=WebhookAckResponse)
@limiter.limit("60/minute")  # Allow Pub/Sub retries but prevent abuse
async def handle_gmail_webhook(
    request: Request,
    pubsub_request: PubSubPushRequest,
    authorization: str | None = Header(None, alias="Authorization"),
) -> WebhookAckResponse:
    """
    Handle Gmail push notifications via Pub/Sub.

    This endpoint is called by Pub/Sub when Gmail detects changes
    to emails with the "Agent Respond" label.

    Security:
    - Verifies Pub/Sub JWT token in Authorization header (in production)
    - Rate limited via slowapi middleware

    Flow:
    1. Verify Pub/Sub authentication token
    2. Decode base64 message data
    3. Fetch history since last check
    4. Process new emails
    5. Update stored history ID
    6. Return 200 to acknowledge

    IMPORTANT: Return 200 quickly to acknowledge. Pub/Sub will retry
    if we don't respond within the timeout.
    """
    # Verify Pub/Sub authentication
    if is_pubsub_auth_enabled():
        try:
            verify_pubsub_token(authorization)
        except PubSubAuthError as e:
            logger.warning(f"Pub/Sub authentication failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))

    logger.info(
        f"Received Gmail webhook, message ID: {pubsub_request.message.messageId}"
    )

    try:
        # 1. Decode the Pub/Sub message
        notification = _decode_pubsub_message(pubsub_request.message.data)
        logger.info(
            f"Gmail notification: email={notification.emailAddress}, "
            f"historyId={notification.historyId}"
        )

        # 2. Get the label ID for "Agent Respond"
        respond_label_id = label_manager.get_label_id(settings.label_agent_respond)
        if respond_label_id is None:
            logger.error(
                "Agent Respond label not found. Run setup_gmail_labels.py first."
            )
            return WebhookAckResponse(status="error", processed=0, skipped=0)

        # 3. Get last processed history ID
        last_history_id = history_tracker.get_last_history_id()

        if last_history_id is None:
            # First time - use the notification's history ID as starting point
            # We'll miss this specific change but catch future ones
            logger.info("First run - initializing history ID")
            history_tracker.update_history_id(notification.historyId)
            return WebhookAckResponse(status="initialized", processed=0, skipped=0)

        # 4. Fetch history changes since last check
        try:
            history_records = gmail_client.get_history(
                start_history_id=last_history_id,
                label_id=respond_label_id,
            )
        except StaleHistoryError:
            logger.warning(
                f"Stored history ID {last_history_id} is stale; "
                "recovering from currently labeled messages"
            )
            fallback_messages = gmail_client.list_messages_with_label(
                label_id=respond_label_id
            )
            processed, skipped = _process_message_refs(
                message_refs=fallback_messages,
                user_email=notification.emailAddress,
            )
            history_tracker.update_history_id(notification.historyId)
            logger.info(
                f"Webhook recovered from stale history: "
                f"processed={processed}, skipped={skipped}"
            )
            return WebhookAckResponse(
                status="recovered",
                processed=processed,
                skipped=skipped,
            )
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
            # Still update history ID to avoid getting stuck
            history_tracker.update_history_id(notification.historyId)
            return WebhookAckResponse(status="history_error", processed=0, skipped=0)

        # 5. Process new messages and label additions
        processed = 0
        skipped = 0
        seen_message_ids = set()  # Avoid processing same message twice

        for record in history_records:
            # Process newly added messages
            record_processed, record_skipped = _process_message_refs(
                message_refs=record.messages_added,
                user_email=notification.emailAddress,
                seen_message_ids=seen_message_ids,
            )
            processed += record_processed
            skipped += record_skipped

            # Process labels added to existing messages
            label_added_messages = []
            for label_record in record.labels_added:
                msg = label_record.get("message", {})
                label_ids = label_record.get("labelIds", [])

                # Only process if Agent Respond label was added
                if respond_label_id not in label_ids:
                    continue

                label_added_messages.append(msg)

            record_processed, record_skipped = _process_message_refs(
                message_refs=label_added_messages,
                user_email=notification.emailAddress,
                seen_message_ids=seen_message_ids,
            )
            processed += record_processed
            skipped += record_skipped

        # 6. Update history ID
        history_tracker.update_history_id(notification.historyId)

        logger.info(f"Webhook complete: processed={processed}, skipped={skipped}")
        return WebhookAckResponse(status="ok", processed=processed, skipped=skipped)

    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        # Still return 200 to acknowledge - Pub/Sub will retry on non-2xx
        # but we don't want infinite retries for permanent errors
        return WebhookAckResponse(status="error", processed=0, skipped=0)


@webhook_router.post("/renew-watch", response_model=RenewWatchResponse)
@limiter.limit("10/minute")  # Prevent abuse - rarely needs to be called
async def renew_gmail_watch(request: Request) -> RenewWatchResponse:
    """
    Renew the Gmail watch.

    Called by Cloud Scheduler every 6 days to renew the watch
    before it expires (7 days).

    Can also be called manually to set up or reset the watch.
    Rate limited to prevent abuse.
    """
    logger.info("Renewing Gmail watch...")

    try:
        # Ensure labels exist first
        label_manager.ensure_labels_exist()

        # Renew the watch
        result = watch_service.renew_watch()

        logger.info(f"Watch renewed successfully, expires: {result.expiration}")

        return RenewWatchResponse(
            success=True,
            message="Watch renewed successfully",
            history_id=result.history_id,
            expiration=result.expiration,
        )

    except Exception as e:
        logger.exception(f"Failed to renew watch: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to renew watch: {str(e)}",
        )


@webhook_router.get("/watch-status", response_model=WatchStatusResponse)
@limiter.limit("30/minute")
async def get_watch_status(request: Request) -> WatchStatusResponse:
    """
    Get the current Gmail watch status.

    Returns information about whether a watch is active
    and when it expires.
    """
    try:
        expiration = watch_service.get_watch_expiration()

        return WatchStatusResponse(
            active=expiration is not None,
            expiration=expiration,
            label_name=settings.label_agent_respond,
            pubsub_topic=settings.pubsub_topic,
        )

    except Exception as e:
        logger.error(f"Failed to get watch status: {e}")
        return WatchStatusResponse(
            active=False,
            expiration=None,
            label_name=settings.label_agent_respond,
            pubsub_topic=settings.pubsub_topic,
        )


def _decode_pubsub_message(data: str) -> GmailNotificationData:
    """
    Decode base64-encoded Pub/Sub message data.

    Args:
        data: Base64-encoded JSON string.

    Returns:
        Parsed GmailNotificationData.

    Raises:
        ValueError: If data cannot be decoded or parsed.
    """
    try:
        # Decode base64
        decoded_bytes = base64.urlsafe_b64decode(data)
        decoded_str = decoded_bytes.decode("utf-8")

        # Parse JSON
        notification_dict = json.loads(decoded_str)

        return GmailNotificationData(**notification_dict)

    except Exception as e:
        logger.error(f"Failed to decode Pub/Sub message: {e}")
        raise ValueError(f"Invalid Pub/Sub message data: {e}")


def _process_message(message_id: str, thread_id: str, user_email: str) -> str:
    """
    Process a single email message using the LangGraph agent.

    Args:
        message_id: The Gmail message ID.
        thread_id: The Gmail thread ID.
        user_email: The user's email address (to skip self-sent emails).

    Returns:
        "processed" if email was processed, "skipped" otherwise.
    """
    try:
        # =================================================================
        # IDEMPOTENCY CHECKS (before invoking graph)
        # =================================================================
        if label_manager.has_label(message_id, settings.label_agent_done):
            logger.debug(f"Message {message_id} already done, skipping")
            return "skipped"

        if label_manager.has_label(message_id, settings.label_agent_pending):
            logger.debug(f"Message {message_id} already pending, skipping")
            return "skipped"

        # =================================================================
        # FETCH THREAD
        # =================================================================
        thread_emails = gmail_client.get_thread(thread_id)

        if not thread_emails:
            logger.warning(f"Thread {thread_id} is empty, skipping")
            return "skipped"

        latest_email = thread_emails[-1]

        # =================================================================
        # PRE-FILTERING (skip automated/auto-reply senders)
        # =================================================================
        # Skip emails sent by the user themselves (prevents replying to own replies)
        if latest_email.from_email.lower() == user_email.lower():
            logger.info(f"Skipping self-sent email from: {latest_email.from_email}")
            label_manager.remove_label(message_id, settings.label_agent_respond)
            return "skipped"

        if gmail_client.should_skip_sender(latest_email.from_email):
            logger.info(f"Skipping automated sender: {latest_email.from_email}")
            label_manager.remove_label(message_id, settings.label_agent_respond)
            return "skipped"

        if gmail_client.is_auto_reply(latest_email.subject, latest_email.body):
            logger.info(f"Skipping auto-reply: {latest_email.subject}")
            label_manager.remove_label(message_id, settings.label_agent_respond)
            return "skipped"

        # =================================================================
        # INVOKE LANGGRAPH AGENT
        # =================================================================
        logger.info(
            f"Processing email from {latest_email.from_email}: "
            f"{latest_email.subject[:50]}..."
        )

        # Create initial state for the graph
        initial_state = create_initial_state(
            message_id=message_id,
            thread_id=thread_id,
            thread_emails=thread_emails,
            latest_email=latest_email,
        )

        # Run the agent graph
        final_state = invoke_graph(initial_state)

        # Log the outcome
        outcome = final_state.get("outcome", "unknown")
        error_message = final_state.get("error_message")

        if error_message:
            logger.warning(f"Agent completed with error: {error_message}")
        else:
            logger.info(f"Agent completed: outcome={outcome}")

        return "processed"

    except Exception as e:
        logger.exception(f"Error processing message {message_id}: {e}")
        return "skipped"


def _process_message_refs(
    message_refs: list[dict],
    user_email: str,
    seen_message_ids: set[str] | None = None,
) -> tuple[int, int]:
    """
    Process a list of Gmail message references.

    Args:
        message_refs: Message dictionaries containing ``id`` and ``threadId``.
        user_email: The user's Gmail address.
        seen_message_ids: Optional de-duplication set shared across batches.

    Returns:
        Tuple of ``(processed, skipped)`` counts.
    """
    processed = 0
    skipped = 0
    message_ids_seen = seen_message_ids if seen_message_ids is not None else set()

    for message_ref in message_refs:
        message_id = message_ref.get("id")
        thread_id = message_ref.get("threadId")

        if not message_id or not thread_id:
            continue

        if message_id in message_ids_seen:
            continue
        message_ids_seen.add(message_id)

        result = _process_message(message_id, thread_id, user_email)
        if result == "processed":
            processed += 1
        else:
            skipped += 1

    return processed, skipped
