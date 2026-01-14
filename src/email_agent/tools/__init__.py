"""
Agent tools module.

Provides tools for the email agent to interact with external services:
- calendar_check: Check calendar availability
- search_emails: Search past emails
- lookup_contact: Look up contact information
"""

from typing import Any
import logging

from email_agent.tools.base import BaseTool, ToolResult, ToolStatus
from email_agent.tools.calendar import CalendarCheckTool, calendar_tool, TimeSlot, CalendarAvailability
from email_agent.tools.email_search import EmailSearchTool, email_search_tool, EmailSummary, SearchResults
from email_agent.tools.contacts import ContactLookupTool, contact_tool, ContactInfo, ContactSearchResults

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def invoke(self, name: str, **kwargs: Any) -> ToolResult:
        """
        Invoke a tool by name with given parameters.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult from tool execution
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult.fail(f"Unknown tool: {name}")

        logger.info(f"Invoking tool: {name} with params: {kwargs}")
        return tool(**kwargs)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools with their schemas."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """
        Get tool definitions formatted for LLM function calling.

        Returns format compatible with OpenAI function calling schema.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            }
            for tool in self._tools.values()
        ]

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools


def create_default_registry() -> ToolRegistry:
    """Create a registry with all default tools."""
    registry = ToolRegistry()
    registry.register(calendar_tool)
    registry.register(email_search_tool)
    registry.register(contact_tool)
    return registry


# Default registry with all tools
tool_registry = create_default_registry()


__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "ToolStatus",
    # Registry
    "ToolRegistry",
    "tool_registry",
    "create_default_registry",
    # Calendar tool
    "CalendarCheckTool",
    "calendar_tool",
    "TimeSlot",
    "CalendarAvailability",
    # Email search tool
    "EmailSearchTool",
    "email_search_tool",
    "EmailSummary",
    "SearchResults",
    # Contacts tool
    "ContactLookupTool",
    "contact_tool",
    "ContactInfo",
    "ContactSearchResults",
]
