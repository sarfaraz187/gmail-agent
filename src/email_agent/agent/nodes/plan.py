"""
PLAN node - LLM-based tool selection.

Analyzes the email and decides which tools (if any) to call.
This is the "brain" of the agent's tool use capability.

Security:
- Sanitizes email content before including in prompts
- Validates tool names against registry
"""

import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from email_agent.agent.state import AgentState
from email_agent.agent.prompts import TOOL_PLANNING_PROMPT
from email_agent.config import settings
from email_agent.security.sanitization import sanitize_for_prompt
from email_agent.tools import tool_registry

logger = logging.getLogger(__name__)


def plan_node(state: AgentState) -> dict:
    """
    Use LLM to decide which tools to call.

    Analyzes the email content and determines:
    - If scheduling mentioned -> calendar_check
    - If referencing past emails -> search_emails
    - If needing contact info -> lookup_contact
    - For simple emails -> no tools needed

    Security:
    - Sanitizes all email content before including in prompt
    - Prevents prompt injection attacks

    Args:
        state: Current agent state with latest_email.

    Returns:
        Updated state fields: tools_to_call, planning_reasoning.
    """
    latest_email = state["latest_email"]
    thread_emails = state["thread_emails"]

    # Sanitize email content to prevent prompt injection
    sanitized_subject = sanitize_for_prompt(latest_email.subject, max_length=500)
    sanitized_body = sanitize_for_prompt(latest_email.body, max_length=10000)

    # Build thread context (previous emails only) with sanitization
    thread_parts = []
    for email in thread_emails[:-1]:
        safe_subject = sanitize_for_prompt(email.subject, max_length=200)
        safe_body = sanitize_for_prompt(email.body, max_length=2000)
        thread_parts.append(
            f"From: {email.from_email}\nSubject: {safe_subject}\n{safe_body}"
        )
    thread_context = "\n---\n".join(thread_parts) or "No previous emails in thread"

    # Get tool descriptions from registry
    tools_list = tool_registry.list_tools()
    tools_description = "\n".join(
        [f"- {t['name']}: {t['description']}" for t in tools_list]
    )

    # Format the prompt with sanitized content
    prompt = TOOL_PLANNING_PROMPT.format(
        sender_email=latest_email.from_email,
        subject=sanitized_subject,
        body=sanitized_body,
        thread_context=thread_context,
        tools_description=tools_description,
    )

    logger.info("Planning: Analyzing email for tool requirements")

    # Call LLM with lower temperature for consistent planning
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,  # Lower for consistent planning decisions
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()

        # Try to extract JSON from response
        # Handle case where LLM wraps JSON in markdown code block
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        result = json.loads(response_text)
        tools_to_call = result.get("tools", [])
        reasoning = result.get("reasoning", "")

        # Validate tool names against registry
        valid_tools = []
        for tool_call in tools_to_call:
            tool_name = tool_call.get("name", "")
            if tool_name in tool_registry:
                valid_tools.append(tool_call)
            else:
                logger.warning(f"Unknown tool '{tool_name}' in plan, skipping")

        logger.info(
            f"Planning complete: {len(valid_tools)} tool(s) to call. "
            f"Reasoning: {reasoning}"
        )

        return {
            "tools_to_call": valid_tools,
            "planning_reasoning": reasoning,
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse planning response as JSON: {e}")
        logger.debug(f"Raw response: {response_text}")

        return {
            "tools_to_call": [],
            "planning_reasoning": "Planning failed (JSON parse error), proceeding without tools",
        }

    except Exception as e:
        logger.error(f"Planning failed: {e}")

        return {
            "tools_to_call": [],
            "planning_reasoning": f"Planning failed ({e}), proceeding without tools",
        }
