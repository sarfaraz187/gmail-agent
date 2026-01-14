"""Tests for the execute node."""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.execute import execute_node
from email_agent.tools.base import ToolResult


@dataclass
class MockEmailData:
    """Mock EmailData for testing."""
    message_id: str = "msg123"
    thread_id: str = "thread123"
    subject: str = "Test Subject"
    from_email: str = "sender@example.com"
    from_name: str = "Sender"
    to_email: str = "user@example.com"
    date: str = "2025-01-11"
    body: str = "Test email body"
    snippet: str = "Test snippet"
    labels: list = None
    rfc_message_id: str = None
    in_reply_to: str = None
    references: str = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


class TestExecuteNode:
    """Tests for execute_node function."""

    @pytest.fixture
    def mock_registry(self):
        """Mock tool registry."""
        with patch("email_agent.agent.nodes.execute.tool_registry") as mock:
            yield mock

    @pytest.fixture
    def base_state(self):
        """Create base state without tools."""
        latest = MockEmailData()
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
            "tools_to_call": [],
        }

    def test_execute_no_tools(self, mock_registry, base_state):
        """Test execution with no tools to call."""
        result = execute_node(base_state)

        assert result["tool_results"] == {}
        mock_registry.invoke.assert_not_called()

    def test_execute_single_tool_success(self, mock_registry, base_state):
        """Test successful execution of a single tool."""
        base_state["tools_to_call"] = [
            {"name": "calendar_check", "args": {"start_date": "tomorrow"}}
        ]

        mock_result = ToolResult.ok({
            "available_slots": ["10:00 AM", "2:00 PM"],
            "summary": "2 slots available tomorrow"
        })
        mock_registry.invoke.return_value = mock_result

        result = execute_node(base_state)

        assert "calendar_check" in result["tool_results"]
        assert result["tool_results"]["calendar_check"].success
        mock_registry.invoke.assert_called_once_with(
            "calendar_check",
            start_date="tomorrow"
        )

    def test_execute_multiple_tools(self, mock_registry, base_state):
        """Test execution of multiple tools."""
        base_state["tools_to_call"] = [
            {"name": "calendar_check", "args": {"start_date": "tomorrow"}},
            {"name": "search_emails", "args": {"query": "proposal"}}
        ]

        mock_registry.invoke.side_effect = [
            ToolResult.ok({"summary": "Calendar result"}),
            ToolResult.ok({"summary": "Email search result"})
        ]

        result = execute_node(base_state)

        assert len(result["tool_results"]) == 2
        assert "calendar_check" in result["tool_results"]
        assert "search_emails" in result["tool_results"]

    def test_execute_tool_failure(self, mock_registry, base_state):
        """Test handling of tool failure."""
        base_state["tools_to_call"] = [
            {"name": "calendar_check", "args": {"start_date": "tomorrow"}}
        ]

        mock_result = ToolResult.fail("Calendar service unavailable")
        mock_registry.invoke.return_value = mock_result

        result = execute_node(base_state)

        assert "calendar_check" in result["tool_results"]
        assert not result["tool_results"]["calendar_check"].success
        assert "unavailable" in result["tool_results"]["calendar_check"].error

    def test_execute_tool_exception(self, mock_registry, base_state):
        """Test handling of tool exception."""
        base_state["tools_to_call"] = [
            {"name": "calendar_check", "args": {"start_date": "tomorrow"}}
        ]

        mock_registry.invoke.side_effect = Exception("Connection timeout")

        result = execute_node(base_state)

        assert "calendar_check" in result["tool_results"]
        assert not result["tool_results"]["calendar_check"].success
        assert "Connection timeout" in result["tool_results"]["calendar_check"].error

    def test_execute_partial_failure(self, mock_registry, base_state):
        """Test execution when some tools succeed and others fail."""
        base_state["tools_to_call"] = [
            {"name": "calendar_check", "args": {"start_date": "tomorrow"}},
            {"name": "search_emails", "args": {"query": "proposal"}}
        ]

        mock_registry.invoke.side_effect = [
            ToolResult.ok({"summary": "Calendar result"}),
            Exception("Search failed")
        ]

        result = execute_node(base_state)

        assert result["tool_results"]["calendar_check"].success
        assert not result["tool_results"]["search_emails"].success

    def test_execute_with_empty_args(self, mock_registry, base_state):
        """Test tool execution with empty args."""
        base_state["tools_to_call"] = [
            {"name": "lookup_contact", "args": {}}
        ]

        mock_result = ToolResult.ok({"summary": "Contact found"})
        mock_registry.invoke.return_value = mock_result

        result = execute_node(base_state)

        mock_registry.invoke.assert_called_once_with("lookup_contact")
        assert result["tool_results"]["lookup_contact"].success

    def test_execute_missing_name(self, mock_registry, base_state):
        """Test handling of tool call missing name."""
        base_state["tools_to_call"] = [
            {"args": {"start_date": "tomorrow"}}  # Missing "name"
        ]

        result = execute_node(base_state)

        # Should attempt to invoke with empty string name
        mock_registry.invoke.assert_called_once()
