"""
CLASSIFY node - Email classification.

Determines if the email can be auto-responded to or requires user input.
Wraps the existing email_classifier.
"""

import logging

from email_agent.agent.classifier import email_classifier
from email_agent.agent.state import AgentState

logger = logging.getLogger(__name__)


def classify_node(state: AgentState) -> dict:
    """
    Classify the email to determine response path.

    Uses the existing email_classifier to determine:
    - AUTO_RESPOND: Email can be handled automatically
    - NEEDS_CHOICE/NEEDS_APPROVAL/NEEDS_INPUT: User decision required

    Args:
        state: Current agent state with latest_email.

    Returns:
        Updated state fields: classification, detected_language.
    """
    latest_email = state["latest_email"]
    thread_emails = state["thread_emails"]

    # Build thread context from previous emails (excluding the latest)
    thread_context = [email.body for email in thread_emails[:-1]]

    logger.info(
        f"Classifying email from {latest_email.from_email}: "
        f"{latest_email.subject[:50]}..."
    )

    # Use existing classifier
    classification = email_classifier.classify(
        subject=latest_email.subject,
        body=latest_email.body,
        sender_email=latest_email.from_email,
        thread_context=thread_context,
    )

    # Detect language for response generation
    detected_language = email_classifier.detect_language(
        f"{latest_email.subject}\n{latest_email.body}"
    )

    logger.info(
        f"Classification: decision={classification.decision.value}, "
        f"type={classification.email_type.value}, "
        f"confidence={classification.confidence:.2f}, "
        f"language={detected_language}"
    )

    return {
        "classification": classification,
        "detected_language": detected_language,
    }
