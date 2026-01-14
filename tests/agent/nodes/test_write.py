"""Tests for the write node."""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.write import (
    write_node,
    _extract_name_from_email,
    _format_tool_context,
)
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


class TestWriteNode:
    """Tests for write_node function."""

    @pytest.fixture
    def mock_draft_generator(self):
        """Mock draft generator."""
        with patch("email_agent.agent.nodes.write.draft_generator") as mock:
            mock.generate_draft.return_value = (
                "Thank you for your email.",
                "formal",
                0.85
            )
            yield mock

    @pytest.fixture
    def mock_email_formatter(self):
        """Mock email formatter."""
        with patch("email_agent.agent.nodes.write.email_formatter") as mock:
            mock.format_email.return_value = (
                "<p>Thank you for your email.</p><br>Signature",
                "Thank you for your email.\n\nSignature"
            )
            yield mock

    @pytest.fixture
    def mock_user_config(self):
        """Mock user config."""
        with patch("email_agent.agent.nodes.write.get_user_config") as mock:
            config = MagicMock()
            config.email = "user@example.com"
            config.signature_html = "<br>Best regards"
            mock.return_value = config
            yield mock

    @pytest.fixture
    def sample_state(self):
        """Create sample state."""
        latest = MockEmailData(
            from_email="John Doe <john@example.com>",
            subject="Meeting request",
            body="Can we meet tomorrow?"
        )
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
            "tool_results": {},
        }

    def test_write_generates_draft(
        self, mock_draft_generator, mock_email_formatter, mock_user_config, sample_state
    ):
        """Test basic draft generation."""
        result = write_node(sample_state)

        assert "draft_body" in result
        assert "html_body" in result
        assert "plain_body" in result
        mock_draft_generator.generate_draft.assert_called_once()

    def test_write_with_tool_context(
        self, mock_draft_generator, mock_email_formatter, mock_user_config, sample_state
    ):
        """Test draft generation with tool results."""
        sample_state["tool_results"] = {
            "calendar_check": ToolResult.ok({
                "summary": "Available: 10am, 2pm, 4pm"
            })
        }

        write_node(sample_state)

        # Verify draft generator was called with enhanced body
        call_args = mock_draft_generator.generate_draft.call_args
        thread = call_args.kwargs["thread"]
        # The last email's body should be enhanced with tool context
        assert "Agent context" in thread[-1]["body"] or "calendar" in str(call_args).lower()

    def test_write_extracts_recipient_name(
        self, mock_draft_generator, mock_email_formatter, mock_user_config, sample_state
    ):
        """Test that recipient name is extracted from email."""
        sample_state["latest_email"].from_email = "John Doe <john@example.com>"

        write_node(sample_state)

        call_args = mock_draft_generator.generate_draft.call_args
        assert call_args.kwargs["recipient_name"] == "John Doe"

    def test_write_handles_generation_failure(
        self, mock_draft_generator, mock_email_formatter, mock_user_config, sample_state
    ):
        """Test handling of draft generation failure."""
        mock_draft_generator.generate_draft.side_effect = Exception("LLM error")

        with pytest.raises(Exception, match="LLM error"):
            write_node(sample_state)


class TestExtractNameFromEmail:
    """Tests for _extract_name_from_email helper."""

    def test_extract_name_with_angle_brackets(self):
        """Test extracting name from 'Name <email>' format."""
        assert _extract_name_from_email("John Doe <john@example.com>") == "John Doe"

    def test_extract_name_with_quotes(self):
        """Test extracting name from '"Name" <email>' format."""
        assert _extract_name_from_email('"John Doe" <john@example.com>') == "John Doe"

    def test_extract_name_plain_email(self):
        """Test plain email without name."""
        assert _extract_name_from_email("john@example.com") == ""

    def test_extract_name_empty_string(self):
        """Test empty string input."""
        assert _extract_name_from_email("") == ""


class TestFormatToolContext:
    """Tests for _format_tool_context helper."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        assert _format_tool_context({}) == ""

    def test_format_calendar_result(self):
        """Test formatting calendar check result."""
        results = {
            "calendar_check": ToolResult.ok({
                "summary": "Available: 10am-12pm"
            })
        }
        formatted = _format_tool_context(results)
        assert "Calendar availability" in formatted
        assert "10am-12pm" in formatted

    def test_format_email_search_result(self):
        """Test formatting email search result."""
        results = {
            "search_emails": ToolResult.ok({
                "summary": "Found 3 relevant emails"
            })
        }
        formatted = _format_tool_context(results)
        assert "Email search results" in formatted

    def test_format_contact_result(self):
        """Test formatting contact lookup result."""
        results = {
            "lookup_contact": ToolResult.ok({
                "summary": "John Doe - CEO at Example Corp"
            })
        }
        formatted = _format_tool_context(results)
        assert "Contact info" in formatted

    def test_format_failed_result(self):
        """Test formatting failed tool result."""
        results = {
            "calendar_check": ToolResult.fail("Service unavailable")
        }
        formatted = _format_tool_context(results)
        assert "Error" in formatted
        assert "unavailable" in formatted

    def test_format_multiple_results(self):
        """Test formatting multiple tool results."""
        results = {
            "calendar_check": ToolResult.ok({"summary": "Calendar info"}),
            "search_emails": ToolResult.ok({"summary": "Email info"})
        }
        formatted = _format_tool_context(results)
        assert "Calendar" in formatted
        assert "Email" in formatted
