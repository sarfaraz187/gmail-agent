"""
Webhook endpoints for Gmail push notifications via Pub/Sub.

These endpoints handle:
- POST /webhook/gmail: Receives Pub/Sub push notifications from Gmail
- POST /renew-watch: Renews Gmail watch (called by Cloud Scheduler)
- GET /watch-status: Check current watch status
"""

import base64
import json
import logging

from fastapi import APIRouter, HTTPException

from email_agent.api.schemas import (
    GmailNotificationData,
    PubSubPushRequest,
    RenewWatchResponse,
    WatchStatusResponse,
    WebhookAckResponse,
)
from email_agent.config import settings
from email_agent.gmail import gmail_client, label_manager, watch_service
from email_agent.storage import history_tracker

logger = logging.getLogger(__name__)

# Create router for webhook endpoints
webhook_router = APIRouter(tags=["webhook"])


@webhook_router.post("/webhook/gmail", response_model=WebhookAckResponse)
async def handle_gmail_webhook(request: PubSubPushRequest) -> WebhookAckResponse:
    """
    Handle Gmail push notifications via Pub/Sub.

    This endpoint is called by Pub/Sub when Gmail detects changes
    to emails with the "Agent Respond" label.

    Flow:
    1. Decode base64 message data
    2. Fetch history since last check
    3. Process new emails
    4. Update stored history ID
    5. Return 200 to acknowledge

    IMPORTANT: Return 200 quickly to acknowledge. Pub/Sub will retry
    if we don't respond within the timeout.
    """
    logger.info(f"Received Gmail webhook, message ID: {request.message.messageId}")

    try:
        # 1. Decode the Pub/Sub message
        notification = _decode_pubsub_message(request.message.data)
        logger.info(
            f"Gmail notification: email={notification.emailAddress}, "
            f"historyId={notification.historyId}"
        )

        # 2. Get the label ID for "Agent Respond"
        respond_label_id = label_manager.get_label_id(settings.label_agent_respond)
        if respond_label_id is None:
            logger.error("Agent Respond label not found. Run setup_gmail_labels.py first.")
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
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
            # Still update history ID to avoid getting stuck
            history_tracker.update_history_id(notification.historyId)
            return WebhookAckResponse(status="history_error", processed=0, skipped=0)

        # 5. Process new messages
        processed = 0
        skipped = 0

        for record in history_records:
            for msg in record.messages_added:
                message_id = msg.get("id")
                thread_id = msg.get("threadId")

                if not message_id or not thread_id:
                    continue

                result = _process_message(message_id, thread_id)
                if result == "processed":
                    processed += 1
                else:
                    skipped += 1

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
async def renew_gmail_watch() -> RenewWatchResponse:
    """
    Renew the Gmail watch.

    Called by Cloud Scheduler every 6 days to renew the watch
    before it expires (7 days).

    Can also be called manually to set up or reset the watch.
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
async def get_watch_status() -> WatchStatusResponse:
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


def _process_message(message_id: str, thread_id: str) -> str:
    """
    Process a single email message.

    Args:
        message_id: The Gmail message ID.
        thread_id: The Gmail thread ID.

    Returns:
        "processed" if email was processed, "skipped" otherwise.
    """
    try:
        # Check if already processed (idempotency)
        if label_manager.has_label(message_id, settings.label_agent_done):
            logger.debug(f"Message {message_id} already done, skipping")
            return "skipped"

        if label_manager.has_label(message_id, settings.label_agent_pending):
            logger.debug(f"Message {message_id} already pending, skipping")
            return "skipped"

        # Fetch the full thread for context
        thread_emails = gmail_client.get_thread(thread_id)

        if not thread_emails:
            logger.warning(f"Thread {thread_id} is empty, skipping")
            return "skipped"

        # Get the latest email in the thread
        latest_email = thread_emails[-1]

        # Skip automated senders
        if gmail_client.should_skip_sender(latest_email.from_email):
            logger.info(f"Skipping automated sender: {latest_email.from_email}")
            # Remove the Agent Respond label since we won't handle it
            label_manager.remove_label(message_id, settings.label_agent_respond)
            return "skipped"

        # Skip auto-replies (out of office, etc.)
        if gmail_client.is_auto_reply(latest_email.subject, latest_email.body):
            logger.info(f"Skipping auto-reply: {latest_email.subject}")
            label_manager.remove_label(message_id, settings.label_agent_respond)
            return "skipped"

        # =================================================================
        # MVP BEHAVIOR: Mark as pending for user review
        # =================================================================
        # In future phases, this is where the agent will:
        # 1. Analyze the email content
        # 2. Decide if it can auto-respond or needs user input
        # 3. Generate a draft response
        # 4. Send the response or mark as pending
        #
        # For now, we just mark everything as pending.
        # =================================================================

        logger.info(
            f"Processing email from {latest_email.from_email}: "
            f"{latest_email.subject[:50]}..."
        )

        # Transition to pending (removes Agent Respond, adds Agent Pending)
        label_manager.transition_to_pending(message_id)

        logger.info(f"Marked message {message_id} as Agent Pending")
        return "processed"

    except Exception as e:
        logger.exception(f"Error processing message {message_id}: {e}")
        return "skipped"
