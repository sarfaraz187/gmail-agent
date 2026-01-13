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

from email_agent.agent import DecisionType, email_classifier
from email_agent.api.schemas import (
    GmailNotificationData,
    PubSubPushRequest,
    RenewWatchResponse,
    WatchStatusResponse,
    WebhookAckResponse,
)
from email_agent.config import settings
from email_agent.gmail import gmail_client, label_manager, watch_service
from email_agent.gmail.client import EmailData
from email_agent.services.draft_generator import draft_generator
from email_agent.services.email_formatter import email_formatter
from email_agent.storage import history_tracker
from email_agent.user_config import get_user_config

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

        # 5. Process new messages and label additions
        processed = 0
        skipped = 0
        seen_message_ids = set()  # Avoid processing same message twice

        for record in history_records:
            # Process newly added messages
            for msg in record.messages_added:
                message_id = msg.get("id")
                thread_id = msg.get("threadId")

                if not message_id or not thread_id:
                    continue

                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)

                result = _process_message(message_id, thread_id)
                if result == "processed":
                    processed += 1
                else:
                    skipped += 1

            # Process labels added to existing messages
            for label_record in record.labels_added:
                msg = label_record.get("message", {})
                label_ids = label_record.get("labelIds", [])

                # Only process if Agent Respond label was added
                if respond_label_id not in label_ids:
                    continue

                message_id = msg.get("id")
                thread_id = msg.get("threadId")

                if not message_id or not thread_id:
                    continue

                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)

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
        # CLASSIFY EMAIL
        # =================================================================
        # Use the classifier to determine if we can auto-respond
        # or if user input is required.
        # =================================================================

        logger.info(
            f"Classifying email from {latest_email.from_email}: "
            f"{latest_email.subject[:50]}..."
        )

        # Build thread context from previous emails
        thread_context = [email.body for email in thread_emails[:-1]]

        # Classify the email
        classification = email_classifier.classify(
            subject=latest_email.subject,
            body=latest_email.body,
            sender_email=latest_email.from_email,
            thread_context=thread_context,
        )

        # Detect language for future response generation
        detected_language = email_classifier.detect_language(
            f"{latest_email.subject}\n{latest_email.body}"
        )

        logger.info(
            f"Classification: decision={classification.decision.value}, "
            f"type={classification.email_type.value}, "
            f"confidence={classification.confidence:.2f}, "
            f"language={detected_language}, "
            f"reason={classification.reason}"
        )

        # =================================================================
        # HANDLE BASED ON DECISION TYPE
        # =================================================================
        if classification.decision == DecisionType.AUTO_RESPOND:
            # =============================================================
            # AUTO-RESPOND PATH
            # =============================================================
            # 1. Generate a draft response using LLM
            # 2. Append user signature
            # 3. Send the response via Gmail API
            # 4. Mark as "Agent Done"
            # =============================================================
            logger.info(
                f"Email classified as AUTO_RESPOND ({classification.email_type.value}). "
                f"Generating and sending response..."
            )

            try:
                # Generate the draft (returns both HTML and plain text)
                html_body, plain_body = _generate_auto_response(
                    thread_emails=thread_emails,
                    latest_email=latest_email,
                )

                # Build proper References header for threading
                # References should be: original References + Message-ID of email being replied to
                references = latest_email.references or ""
                if latest_email.rfc_message_id:
                    if references:
                        references = f"{references} {latest_email.rfc_message_id}"
                    else:
                        references = latest_email.rfc_message_id

                # Send the reply with proper threading headers
                # in_reply_to: The RFC 2822 Message-ID of the email we're replying to
                # references: Chain of Message-IDs in the thread
                gmail_client.send_reply(
                    thread_id=thread_id,
                    to=latest_email.from_email,
                    subject=latest_email.subject,
                    body=plain_body,
                    html_body=html_body,
                    in_reply_to=latest_email.rfc_message_id,
                    references=references if references else None,
                )

                # Transition to Done
                label_manager.transition_to_done(message_id)
                logger.info(f"Successfully auto-responded to message {message_id}")
                return "processed"

            except Exception as e:
                logger.error(f"Failed to auto-respond to {message_id}: {e}")
                # Fall back to pending if auto-respond fails
                label_manager.transition_to_pending(message_id)
                logger.info(f"Marked message {message_id} as Agent Pending (auto-respond failed)")
                return "processed"

        else:
            # =============================================================
            # NEEDS USER INPUT PATH
            # =============================================================
            # Decision types: NEEDS_CHOICE, NEEDS_APPROVAL, NEEDS_INPUT
            # Mark as "Agent Pending" for user to review.
            # =============================================================
            logger.info(
                f"Email requires user input: {classification.decision.value}. "
                f"Reason: {classification.reason}"
            )
            label_manager.transition_to_pending(message_id)
            logger.info(f"Marked message {message_id} as Agent Pending")
            return "processed"

    except Exception as e:
        logger.exception(f"Error processing message {message_id}: {e}")
        return "skipped"


def _generate_auto_response(
    thread_emails: list[EmailData],
    latest_email: EmailData,
) -> tuple[str, str]:
    """
    Generate an auto-response for the email.

    Uses the draft generator to create a response based on the email
    thread context, then formats as HTML with signature.

    Args:
        thread_emails: Full email thread for context.
        latest_email: The email to respond to.

    Returns:
        Tuple of (html_body, plain_text_body).
    """
    # Get user config for signature
    user_config = get_user_config()

    # Convert EmailData objects to dict format expected by draft_generator
    thread_dicts = [
        {
            "from_": email.from_email,
            "to": email.to_email,
            "subject": email.subject,
            "date": email.date,
            "body": email.body,
        }
        for email in thread_emails
    ]

    # Generate the draft (without signature - we'll add it via formatter)
    draft_body, detected_tone, confidence = draft_generator.generate_draft(
        thread=thread_dicts,
        user_email=user_config.email or latest_email.to_email,
        subject=latest_email.subject,
    )

    logger.info(f"Generated draft with tone={detected_tone}, confidence={confidence:.2f}")

    # Format as HTML with signature
    html_body, plain_body = email_formatter.format_email(
        body=draft_body,
        signature_html=user_config.signature_html,
    )

    return html_body, plain_body
