"""
SEND node - Email sending.

Sends the generated reply and marks the email as done.
Also triggers learning from the sent email.
"""

import logging

from email_agent.agent.state import AgentState
from email_agent.gmail import gmail_client, label_manager

logger = logging.getLogger(__name__)


def send_node(state: AgentState) -> dict:
    """
    Send the reply and transition to done.

    1. Sends the email via Gmail API with proper threading
    2. Marks the email as "Agent Done"
    3. Triggers learning from the sent email (fire-and-forget)

    Args:
        state: Current agent state with draft ready.

    Returns:
        Updated state fields: outcome, error_message.
    """
    message_id = state["message_id"]
    thread_id = state["thread_id"]
    latest_email = state["latest_email"]
    plain_body = state["plain_body"]
    html_body = state["html_body"]
    draft_body = state["draft_body"]
    thread_emails = state["thread_emails"]

    logger.info(f"Sending reply to message {message_id}")

    try:
        # Build proper References header for threading
        # References should be: original References + Message-ID of email being replied to
        references = latest_email.references or ""
        if latest_email.rfc_message_id:
            if references:
                references = f"{references} {latest_email.rfc_message_id}"
            else:
                references = latest_email.rfc_message_id

        # Send the reply
        gmail_client.send_reply(
            thread_id=thread_id,
            to=latest_email.from_email,
            subject=latest_email.subject,
            body=plain_body,
            html_body=html_body,
            in_reply_to=latest_email.rfc_message_id,
            references=references if references else None,
        )

        logger.info(f"Reply sent successfully for message {message_id}")

        # Transition to done
        label_manager.transition_to_done(message_id)
        logger.info(f"Message {message_id} marked as Agent Done")

        # Trigger learning (fire-and-forget)
        _trigger_learning(
            sent_body=draft_body,
            recipient_email=latest_email.from_email,
            recipient_name=_extract_name_from_email(latest_email.from_email),
            thread_context=[email.body for email in thread_emails[:-1]],
        )

        return {
            "outcome": "sent",
            "error_message": None,
        }

    except Exception as e:
        logger.error(f"Failed to send reply: {e}")

        # Fall back to pending if send fails
        try:
            label_manager.transition_to_pending(message_id)
            logger.info(f"Message {message_id} marked as pending (send failed)")
        except Exception as label_error:
            logger.error(f"Failed to mark as pending: {label_error}")

        return {
            "outcome": "error",
            "error_message": str(e),
        }


def _extract_name_from_email(from_email: str) -> str:
    """Extract name from email address if available."""
    import re

    match = re.match(r'^"?([^"<]+)"?\s*<', from_email)
    if match:
        return match.group(1).strip()
    return ""


def _trigger_learning(
    sent_body: str,
    recipient_email: str,
    recipient_name: str,
    thread_context: list[str],
) -> None:
    """
    Learn from sent email and update contact memory.

    This is fire-and-forget - failures are logged but don't affect
    the main send flow.

    Args:
        sent_body: The body of the sent email.
        recipient_email: Recipient's email address.
        recipient_name: Recipient's name (if known).
        thread_context: Previous emails in thread for context.
    """
    try:
        from email_agent.services.style_learner import style_learner

        style_learner.learn_from_sent_email(
            sent_body=sent_body,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            thread_context=thread_context,
        )
        logger.debug(f"Learning triggered for {recipient_email}")

    except Exception as e:
        # Non-critical - log and continue
        logger.warning(f"Failed to learn from sent email: {e}")
