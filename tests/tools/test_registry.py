"""Tests for tool registry."""

from typing import Any
from unittest.mock import MagicMock
import pytest

from email_agent.tools import (
    ToolRegistry,
    tool_registry,
    create_default_registry,
    BaseTool,
    ToolResult,
)


class MockTool(BaseTool):
    """Mock tool for testing registry."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        }

    def execute(self, message: str, **kwargs: Any) -> ToolResult:
        return ToolResult.ok({"echo": message})


class AnotherMockTool(BaseTool):
    """Another mock tool for testing."""

    @property
    def name(self) -> str:
        return "another_tool"

    @property
    def description(self) -> str:
        return "Another mock tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok("success")


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create fresh registry for each test."""
        return ToolRegistry()

    def test_register_tool(self, registry):
        """Test registering a tool."""
        tool = MockTool()
        registry.register(tool)

        assert "mock_tool" in registry
        assert len(registry) == 1

    def test_register_multiple_tools(self, registry):
        """Test registering multiple tools."""
        registry.register(MockTool())
        registry.register(AnotherMockTool())

        assert len(registry) == 2
        assert "mock_tool" in registry
        assert "another_tool" in registry

    def test_register_overwrites_existing(self, registry):
        """Test that registering with same name overwrites."""
        tool1 = MockTool()
        tool2 = MockTool()

        registry.register(tool1)
        registry.register(tool2)

        assert len(registry) == 1

    def test_get_existing_tool(self, registry):
        """Test getting an existing tool."""
        tool = MockTool()
        registry.register(tool)

        result = registry.get("mock_tool")

        assert result is tool

    def test_get_nonexistent_tool(self, registry):
        """Test getting a nonexistent tool returns None."""
        result = registry.get("nonexistent")
        assert result is None

    def test_invoke_success(self, registry):
        """Test invoking a tool successfully."""
        registry.register(MockTool())

        result = registry.invoke("mock_tool", message="hello")

        assert result.success is True
        assert result.data == {"echo": "hello"}

    def test_invoke_unknown_tool(self, registry):
        """Test invoking unknown tool returns error."""
        result = registry.invoke("nonexistent", param="value")

        assert result.success is False
        assert "Unknown tool" in result.error

    def test_list_tools(self, registry):
        """Test listing all tools."""
        registry.register(MockTool())
        registry.register(AnotherMockTool())

        tools = registry.list_tools()

        assert len(tools) == 2
        assert any(t["name"] == "mock_tool" for t in tools)
        assert any(t["name"] == "another_tool" for t in tools)

    def test_list_tools_has_schema(self, registry):
        """Test that list_tools includes parameter schema."""
        registry.register(MockTool())

        tools = registry.list_tools()

        assert "parameters" in tools[0]
        assert "properties" in tools[0]["parameters"]

    def test_tool_names(self, registry):
        """Test getting tool names."""
        registry.register(MockTool())
        registry.register(AnotherMockTool())

        names = registry.tool_names

        assert set(names) == {"mock_tool", "another_tool"}

    def test_get_tools_for_llm(self, registry):
        """Test getting tools formatted for LLM."""
        registry.register(MockTool())

        tools = registry.get_tools_for_llm()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert "function" in tools[0]
        assert tools[0]["function"]["name"] == "mock_tool"
        assert "description" in tools[0]["function"]
        assert "parameters" in tools[0]["function"]

    def test_contains_true(self, registry):
        """Test __contains__ with existing tool."""
        registry.register(MockTool())
        assert "mock_tool" in registry

    def test_contains_false(self, registry):
        """Test __contains__ with nonexistent tool."""
        assert "nonexistent" not in registry

    def test_len_empty(self, registry):
        """Test len of empty registry."""
        assert len(registry) == 0

    def test_len_with_tools(self, registry):
        """Test len with registered tools."""
        registry.register(MockTool())
        registry.register(AnotherMockTool())
        assert len(registry) == 2


class TestDefaultRegistry:
    """Tests for default registry and factory."""

    def test_create_default_registry(self):
        """Test creating default registry has all tools."""
        registry = create_default_registry()

        assert "calendar_check" in registry
        assert "search_emails" in registry
        assert "lookup_contact" in registry
        assert len(registry) == 3

    def test_global_tool_registry(self):
        """Test that global tool_registry has all tools."""
        assert "calendar_check" in tool_registry
        assert "search_emails" in tool_registry
        assert "lookup_contact" in tool_registry

    def test_tools_have_correct_types(self):
        """Test that registered tools are correct types."""
        from email_agent.tools import (
            CalendarCheckTool,
            EmailSearchTool,
            ContactLookupTool,
        )

        registry = create_default_registry()

        assert isinstance(registry.get("calendar_check"), CalendarCheckTool)
        assert isinstance(registry.get("search_emails"), EmailSearchTool)
        assert isinstance(registry.get("lookup_contact"), ContactLookupTool)
