"""
EXECUTE node - Tool execution.

Executes the tools planned by the PLAN node and collects results.
"""

import logging

from email_agent.agent.state import AgentState
from email_agent.tools import tool_registry

logger = logging.getLogger(__name__)


def execute_node(state: AgentState) -> dict:
    """
    Execute planned tool calls.

    Iterates through tools_to_call and invokes each via tool_registry.
    Results are stored keyed by tool name.

    Args:
        state: Current agent state with tools_to_call.

    Returns:
        Updated state fields: tool_results.
    """
    tools_to_call = state.get("tools_to_call", [])

    if not tools_to_call:
        logger.info("No tools to execute")
        return {"tool_results": {}}

    logger.info(f"Executing {len(tools_to_call)} tool(s)")

    results = {}
    for tool_call in tools_to_call:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})

        logger.info(f"Invoking tool: {tool_name} with args: {tool_args}")

        try:
            result = tool_registry.invoke(tool_name, **tool_args)
            results[tool_name] = result

            if result.success:
                logger.info(f"Tool {tool_name}: success")
            else:
                logger.warning(f"Tool {tool_name}: {result.error}")

        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            # Create a failed result
            from email_agent.tools.base import ToolResult
            results[tool_name] = ToolResult.fail(str(e))

    logger.info(f"Tool execution complete: {len(results)} result(s)")

    return {"tool_results": results}
