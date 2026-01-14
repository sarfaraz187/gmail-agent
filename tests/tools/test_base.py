"""Tests for base tool classes."""

import pytest
from typing import Any

from email_agent.tools.base import BaseTool, ToolResult, ToolStatus


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_ok_creates_success_result(self):
        """Test ToolResult.ok() creates successful result."""
        result = ToolResult.ok({"key": "value"}, extra="metadata")

        assert result.success is True
        assert result.status == ToolStatus.SUCCESS
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.metadata == {"extra": "metadata"}

    def test_fail_creates_error_result(self):
        """Test ToolResult.fail() creates error result."""
        result = ToolResult.fail("Something went wrong", code=500)

        assert result.success is False
        assert result.status == ToolStatus.ERROR
        assert result.data is None
        assert result.error == "Something went wrong"
        assert result.metadata == {"code": 500}

    def test_not_found_creates_not_found_result(self):
        """Test ToolResult.not_found() creates not found result."""
        result = ToolResult.not_found("User not found")

        assert result.success is False
        assert result.status == ToolStatus.NOT_FOUND
        assert result.error == "User not found"

    def test_empty_creates_no_results_result(self):
        """Test ToolResult.empty() creates empty result."""
        result = ToolResult.empty("No matching emails")

        assert result.success is False
        assert result.status == ToolStatus.NO_RESULTS
        assert result.data == []
        assert result.error == "No matching emails"


class MockTool(BaseTool):
    """Mock tool for testing."""

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
                "required_param": {"type": "string"},
                "optional_param": {"type": "integer", "default": 10},
            },
            "required": ["required_param"],
        }

    def execute(self, required_param: str, optional_param: int = 10, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(
            {"required": required_param, "optional": optional_param}
        )


class FailingTool(BaseTool):
    """Tool that always raises exception."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "A tool that always fails"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        raise ValueError("Intentional failure")


class TestBaseTool:
    """Tests for BaseTool base class."""

    def test_validate_params_success(self):
        """Test parameter validation with valid params."""
        tool = MockTool()
        is_valid, error = tool.validate_params(required_param="test")

        assert is_valid is True
        assert error is None

    def test_validate_params_missing_required(self):
        """Test parameter validation with missing required param."""
        tool = MockTool()
        is_valid, error = tool.validate_params(optional_param=5)

        assert is_valid is False
        assert "required_param" in error

    def test_validate_params_none_value(self):
        """Test parameter validation with None value for required param."""
        tool = MockTool()
        is_valid, error = tool.validate_params(required_param=None)

        assert is_valid is False
        assert "required_param" in error

    def test_call_executes_tool(self):
        """Test __call__ executes tool correctly."""
        tool = MockTool()
        result = tool(required_param="hello", optional_param=20)

        assert result.success is True
        assert result.data == {"required": "hello", "optional": 20}

    def test_call_validates_before_execute(self):
        """Test __call__ validates params before executing."""
        tool = MockTool()
        result = tool()  # Missing required_param

        assert result.success is False
        assert "required_param" in result.error

    def test_call_catches_exceptions(self):
        """Test __call__ catches and wraps exceptions."""
        tool = FailingTool()
        result = tool()

        assert result.success is False
        assert "Intentional failure" in result.error

    def test_tool_properties(self):
        """Test tool property accessors."""
        tool = MockTool()

        assert tool.name == "mock_tool"
        assert "mock tool for testing" in tool.description.lower()
        assert "required_param" in tool.parameters_schema["properties"]
