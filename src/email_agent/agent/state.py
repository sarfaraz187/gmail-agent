"""
Agent state definition for LangGraph.

This module defines the AgentState TypedDict that flows through
the LangGraph state machine nodes.
"""

from typing import TypedDict

from email_agent.agent.classifier import DecisionResult
from email_agent.gmail.client import EmailData
from email_agent.tools.base import ToolResult


class AgentState(TypedDict):
    """
    State that flows through the LangGraph agent.

    This state is initialized by the webhook and passed through each node.
    Each node reads what it needs and adds its outputs.
    """

    # ==========================================================================
    # INPUT (set by webhook before invoking graph)
    # ==========================================================================
    message_id: str  # Gmail's internal API message ID
    thread_id: str  # Gmail thread ID
    thread_emails: list[EmailData]  # Full thread, oldest first
    latest_email: EmailData  # The email we're responding to

    # ==========================================================================
    # CLASSIFICATION (set by CLASSIFY node)
    # ==========================================================================
    classification: DecisionResult | None  # Result from email_classifier
    detected_language: str  # ISO language code (e.g., "en", "es")

    # ==========================================================================
    # PLANNING (set by PLAN node - LLM decides which tools to call)
    # ==========================================================================
    tools_to_call: list[dict]  # [{"name": "calendar_check", "args": {...}}, ...]
    planning_reasoning: str  # LLM's explanation for tool choices

    # ==========================================================================
    # TOOL EXECUTION (set by EXECUTE node)
    # ==========================================================================
    tool_results: dict[str, ToolResult]  # {"calendar_check": ToolResult, ...}

    # ==========================================================================
    # DRAFT GENERATION (set by WRITE node)
    # ==========================================================================
    draft_body: str  # Raw draft text (without signature)
    html_body: str  # Formatted HTML body (with signature)
    plain_body: str  # Plain text body (with signature)

    # ==========================================================================
    # OUTCOME (set by SEND or NOTIFY node)
    # ==========================================================================
    outcome: str  # "sent", "pending", "error"
    error_message: str | None  # Error details if outcome is "error"


def create_initial_state(
    message_id: str,
    thread_id: str,
    thread_emails: list[EmailData],
    latest_email: EmailData,
) -> AgentState:
    """
    Create an initial AgentState for graph invocation.

    Args:
        message_id: Gmail message ID.
        thread_id: Gmail thread ID.
        thread_emails: Full email thread.
        latest_email: The email to respond to.

    Returns:
        Initialized AgentState with default values.
    """
    return AgentState(
        # Input
        message_id=message_id,
        thread_id=thread_id,
        thread_emails=thread_emails,
        latest_email=latest_email,
        # Classification (populated by CLASSIFY node)
        classification=None,
        detected_language="en",
        # Planning (populated by PLAN node)
        tools_to_call=[],
        planning_reasoning="",
        # Tool execution (populated by EXECUTE node)
        tool_results={},
        # Draft (populated by WRITE node)
        draft_body="",
        html_body="",
        plain_body="",
        # Outcome (populated by SEND or NOTIFY node)
        outcome="",
        error_message=None,
    )
