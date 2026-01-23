"""
SAVE_DRAFT node - Draft creation for pending emails.

Creates a draft reply in Gmail Drafts folder for user review.
Used when email requires human approval/input before sending.
"""

import logging

from email_agent.agent.state import AgentState
from email_agent.gmail import gmail_client, label_manager

logger = logging.getLogger(__name__)


def save_draft_node(state: AgentState) -> dict:
    """
    Save the generated reply as a draft for user review.

    1. Creates a draft in Gmail Drafts folder (linked to thread)
    2. User can review, edit, and send manually

    Args:
        state: Current agent state with draft ready.

    Returns:
        Updated state fields: draft_id.
    """
    message_id = state["message_id"]
    thread_id = state["thread_id"]
    latest_email = state["latest_email"]
    plain_body = state["plain_body"]
    html_body = state["html_body"]

    logger.info(f"Creating draft for message {message_id}")

    try:
        # Build proper References header for threading
        references = latest_email.references or ""
        if latest_email.rfc_message_id:
            if references:
                references = f"{references} {latest_email.rfc_message_id}"
            else:
                references = latest_email.rfc_message_id

        # Create the draft
        draft_id = gmail_client.create_draft(
            thread_id=thread_id,
            to=latest_email.from_email,
            subject=latest_email.subject,
            body=plain_body,
            html_body=html_body,
            in_reply_to=latest_email.rfc_message_id,
            references=references if references else None,
        )

        logger.info(f"Draft created for message {message_id}, draft ID: {draft_id}")

        return {
            "draft_id": draft_id,
        }

    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        return {
            "draft_id": None,
            "error_message": f"Failed to create draft: {e}",
        }
