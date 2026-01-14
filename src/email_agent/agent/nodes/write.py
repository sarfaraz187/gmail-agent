"""
WRITE node - Draft generation.

Generates the email response using the draft generator.
Incorporates tool results into the response context.
"""

import logging

from email_agent.agent.state import AgentState
from email_agent.services.draft_generator import draft_generator
from email_agent.services.email_formatter import email_formatter
from email_agent.tools.base import ToolResult
from email_agent.user_config import get_user_config

logger = logging.getLogger(__name__)


def write_node(state: AgentState) -> dict:
    """
    Generate email draft with tool context.

    Uses the existing draft_generator and email_formatter.
    Tool results are formatted and included in the generation context.

    Args:
        state: Current agent state with tool_results.

    Returns:
        Updated state fields: draft_body, html_body, plain_body.
    """
    latest_email = state["latest_email"]
    thread_emails = state["thread_emails"]
    tool_results = state.get("tool_results", {})

    # Get user config for signature
    user_config = get_user_config()

    # Convert EmailData to dict format for draft_generator
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

    # Extract recipient name from email
    recipient_name = _extract_name_from_email(latest_email.from_email)

    # Format tool context for inclusion in draft
    tool_context_text = _format_tool_context(tool_results)

    if tool_context_text:
        logger.info(f"Including tool context in draft generation")
        # Inject tool context into the thread as a system note
        # This is a simple approach - could be enhanced with a dedicated prompt
        enhanced_body = (
            f"{latest_email.body}\n\n"
            f"[Agent context from tools:\n{tool_context_text}]"
        )
        thread_dicts[-1]["body"] = enhanced_body

    logger.info(f"Generating draft for email from {latest_email.from_email}")

    try:
        # Generate the draft
        draft_body, detected_tone, confidence = draft_generator.generate_draft(
            thread=thread_dicts,
            user_email=user_config.email or latest_email.to_email,
            subject=latest_email.subject,
            recipient_email=latest_email.from_email,
            recipient_name=recipient_name,
        )

        logger.info(
            f"Draft generated: tone={detected_tone}, confidence={confidence:.2f}"
        )

        # Format as HTML with signature
        html_body, plain_body = email_formatter.format_email(
            body=draft_body,
            signature_html=user_config.signature_html,
        )

        return {
            "draft_body": draft_body,
            "html_body": html_body,
            "plain_body": plain_body,
        }

    except Exception as e:
        logger.error(f"Draft generation failed: {e}")
        raise


def _extract_name_from_email(from_email: str) -> str:
    """
    Extract name from email address if available.

    Handles formats like:
    - "John Doe <john@example.com>" -> "John Doe"
    - "john@example.com" -> ""

    Args:
        from_email: Email address, possibly with name.

    Returns:
        Extracted name or empty string.
    """
    import re

    # Match "Name <email>" pattern
    match = re.match(r'^"?([^"<]+)"?\s*<', from_email)
    if match:
        return match.group(1).strip()

    return ""


def _format_tool_context(tool_results: dict[str, ToolResult]) -> str:
    """
    Format tool results for inclusion in draft generation.

    Args:
        tool_results: Dict of tool_name -> ToolResult.

    Returns:
        Formatted string for prompt context.
    """
    if not tool_results:
        return ""

    lines = []
    for tool_name, result in tool_results.items():
        if result.success:
            # Extract summary from tool-specific data
            data = result.data or {}
            if tool_name == "calendar_check":
                summary = data.get("summary", "Calendar data available")
                lines.append(f"Calendar availability:\n{summary}")
            elif tool_name == "search_emails":
                summary = data.get("summary", "Email search results available")
                lines.append(f"Email search results:\n{summary}")
            elif tool_name == "lookup_contact":
                summary = data.get("summary", "Contact info available")
                lines.append(f"Contact info:\n{summary}")
            else:
                # Generic handling
                lines.append(f"{tool_name}: {data}")
        else:
            lines.append(f"{tool_name}: Error - {result.error}")

    return "\n\n".join(lines)
