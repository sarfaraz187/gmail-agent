"""
NOTIFY node - Mark email as pending.

Used when the email requires user decision/input.
Marks the email as "Agent Pending" for user review.
"""

import logging

from email_agent.agent.state import AgentState
from email_agent.gmail import label_manager

logger = logging.getLogger(__name__)


def notify_node(state: AgentState) -> dict:
    """
    Mark email as pending for user decision.

    Transitions the email from "Agent Respond" to "Agent Pending".
    User will see this in Gmail and respond manually.

    Args:
        state: Current agent state.

    Returns:
        Updated state fields: outcome.
    """
    message_id = state["message_id"]
    classification = state.get("classification")

    reason = "Unknown"
    if classification:
        reason = f"{classification.decision.value}: {classification.reason}"

    logger.info(
        f"Marking message {message_id} as Agent Pending. "
        f"Reason: {reason}"
    )

    try:
        label_manager.transition_to_pending(message_id)
        logger.info(f"Successfully marked message {message_id} as pending")

        return {
            "outcome": "pending",
            "error_message": None,
        }

    except Exception as e:
        logger.error(f"Failed to mark message as pending: {e}")

        return {
            "outcome": "error",
            "error_message": f"Failed to transition to pending: {e}",
        }
