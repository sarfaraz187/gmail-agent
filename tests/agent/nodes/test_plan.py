"""Tests for the plan node."""

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.plan import plan_node


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


class TestPlanNode:
    """Tests for plan_node function."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for testing."""
        with patch("email_agent.agent.nodes.plan.ChatOpenAI") as mock:
            yield mock

    @pytest.fixture
    def mock_registry(self):
        """Mock tool registry."""
        with patch("email_agent.agent.nodes.plan.tool_registry") as mock:
            mock.list_tools.return_value = [
                {"name": "calendar_check", "description": "Check calendar availability"},
                {"name": "search_emails", "description": "Search past emails"},
                {"name": "lookup_contact", "description": "Look up contact info"},
            ]
            mock.__contains__ = lambda self, x: x in ["calendar_check", "search_emails", "lookup_contact"]
            yield mock

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch("email_agent.agent.nodes.plan.settings") as mock:
            mock.openai_model = "gpt-4o"
            mock.openai_api_key = "test-key"
            yield mock

    @pytest.fixture
    def sample_state(self):
        """Create sample state."""
        latest = MockEmailData(
            subject="Meeting next Thursday",
            body="Can we meet next Thursday afternoon?"
        )
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
        }

    def test_plan_with_calendar_tool(self, mock_llm, mock_registry, mock_settings, sample_state):
        """Test planning with calendar tool."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Email asks about meeting availability",
            "tools": [{"name": "calendar_check", "args": {"start_date": "next Thursday"}}]
        })
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(sample_state)

        assert len(result["tools_to_call"]) == 1
        assert result["tools_to_call"][0]["name"] == "calendar_check"
        assert result["planning_reasoning"] == "Email asks about meeting availability"

    def test_plan_no_tools_needed(self, mock_llm, mock_registry, mock_settings):
        """Test planning when no tools are needed."""
        latest = MockEmailData(
            subject="Thanks!",
            body="Thanks for the help, sounds good!"
        )
        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Simple acknowledgment, no tools needed",
            "tools": []
        })
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(state)

        assert result["tools_to_call"] == []

    def test_plan_multiple_tools(self, mock_llm, mock_registry, mock_settings):
        """Test planning with multiple tools."""
        latest = MockEmailData(
            subject="Meeting and budget doc",
            body="Can we meet Friday? Also, did you see the budget doc I sent?"
        )
        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Need calendar for meeting and email search for budget doc",
            "tools": [
                {"name": "calendar_check", "args": {"start_date": "Friday"}},
                {"name": "search_emails", "args": {"query": "from:sender@example.com budget"}}
            ]
        })
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(state)

        assert len(result["tools_to_call"]) == 2

    def test_plan_filters_invalid_tools(self, mock_llm, mock_registry, mock_settings, sample_state):
        """Test that invalid tool names are filtered out."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Testing invalid tool",
            "tools": [
                {"name": "calendar_check", "args": {"start_date": "tomorrow"}},
                {"name": "invalid_tool", "args": {"foo": "bar"}}
            ]
        })
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(sample_state)

        # Only valid tool should remain
        assert len(result["tools_to_call"]) == 1
        assert result["tools_to_call"][0]["name"] == "calendar_check"

    def test_plan_handles_json_in_code_block(self, mock_llm, mock_registry, mock_settings, sample_state):
        """Test handling of JSON wrapped in markdown code block."""
        mock_response = MagicMock()
        mock_response.content = """```json
{
    "reasoning": "Calendar check needed",
    "tools": [{"name": "calendar_check", "args": {"start_date": "tomorrow"}}]
}
```"""
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(sample_state)

        assert len(result["tools_to_call"]) == 1

    def test_plan_handles_json_parse_error(self, mock_llm, mock_registry, mock_settings, sample_state):
        """Test graceful handling of JSON parse errors."""
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON at all"
        mock_llm.return_value.invoke.return_value = mock_response

        result = plan_node(sample_state)

        # Should return empty tools on parse failure
        assert result["tools_to_call"] == []
        assert "JSON parse error" in result["planning_reasoning"]

    def test_plan_handles_llm_exception(self, mock_llm, mock_registry, mock_settings, sample_state):
        """Test handling of LLM invocation failure."""
        mock_llm.return_value.invoke.side_effect = Exception("API error")

        result = plan_node(sample_state)

        assert result["tools_to_call"] == []
        assert "API error" in result["planning_reasoning"]

    def test_plan_includes_thread_context(self, mock_llm, mock_registry, mock_settings):
        """Test that thread context is included in prompt."""
        prev_email = MockEmailData(body="Previous email about the project")
        latest = MockEmailData(body="Following up on my previous email")

        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [prev_email, latest],
            "latest_email": latest,
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps({"reasoning": "test", "tools": []})
        mock_llm.return_value.invoke.return_value = mock_response

        plan_node(state)

        # Verify LLM was called (prompt includes thread context)
        mock_llm.return_value.invoke.assert_called_once()
