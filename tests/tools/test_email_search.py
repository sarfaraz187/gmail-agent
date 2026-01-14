"""Tests for email search tool."""

from datetime import datetime
from unittest.mock import MagicMock
import pytest

from email_agent.tools.email_search import (
    EmailSearchTool,
    EmailSummary,
    SearchResults,
)
from email_agent.tools.base import ToolStatus


class TestEmailSummary:
    """Tests for EmailSummary dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        summary = EmailSummary(
            message_id="msg123",
            thread_id="thread456",
            subject="Test Subject",
            sender="john@example.com",
            date=datetime(2026, 1, 15, 10, 30),
            snippet="This is a test email...",
        )
        result = summary.to_dict()

        assert result["message_id"] == "msg123"
        assert result["thread_id"] == "thread456"
        assert result["subject"] == "Test Subject"
        assert result["sender"] == "john@example.com"
        assert "snippet" in result

    def test_str_format(self):
        """Test string representation."""
        summary = EmailSummary(
            message_id="msg123",
            thread_id="thread456",
            subject="Test Subject",
            sender="john@example.com",
            date=datetime(2026, 1, 15, 10, 30),
            snippet="This is a test...",
        )
        result = str(summary)

        assert "john@example.com" in result
        assert "Test Subject" in result
        assert "Jan 15, 2026" in result


class TestSearchResults:
    """Tests for SearchResults dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        results = SearchResults(
            query="from:john proposal",
            total_count=2,
            emails=[
                EmailSummary(
                    message_id="msg1",
                    thread_id="t1",
                    subject="Proposal v1",
                    sender="john@example.com",
                    date=datetime(2026, 1, 10),
                    snippet="Here's the proposal...",
                ),
            ],
        )
        result = results.to_dict()

        assert result["query"] == "from:john proposal"
        assert result["total_count"] == 2
        assert len(result["emails"]) == 1
        assert "summary" in result

    def test_get_summary_with_results(self):
        """Test summary with matching emails."""
        results = SearchResults(
            query="proposal",
            total_count=1,
            emails=[
                EmailSummary(
                    message_id="msg1",
                    thread_id="t1",
                    subject="Proposal",
                    sender="john@example.com",
                    date=datetime(2026, 1, 10),
                    snippet="...",
                ),
            ],
        )
        summary = results.get_summary()

        assert "Found 1 email" in summary
        assert "proposal" in summary

    def test_get_summary_no_results(self):
        """Test summary with no results."""
        results = SearchResults(
            query="nonexistent",
            total_count=0,
            emails=[],
        )
        summary = results.get_summary()

        assert "No emails found" in summary


class TestEmailSearchTool:
    """Tests for EmailSearchTool."""

    @pytest.fixture
    def mock_gmail_service(self):
        """Create mock Gmail service."""
        service = MagicMock()
        return service

    @pytest.fixture
    def tool(self, mock_gmail_service):
        """Create tool with mock service."""
        return EmailSearchTool(gmail_service=mock_gmail_service)

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "search_emails"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters_schema["properties"]
        assert "query" in tool.parameters_schema["required"]

    def test_execute_success(self, tool, mock_gmail_service):
        """Test successful search."""
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}],
            "resultSizeEstimate": 2,
        }
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "snippet": "Test snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "john@example.com"},
                    {"name": "Date", "value": "Mon, 15 Jan 2026 10:00:00 +0000"},
                ]
            },
        }

        result = tool.execute(query="from:john")

        assert result.success is True
        assert "emails" in result.data
        assert result.data["total_count"] == 2

    def test_execute_no_results(self, tool, mock_gmail_service):
        """Test search with no results."""
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": [],
            "resultSizeEstimate": 0,
        }

        result = tool.execute(query="nonexistent xyz123")

        assert result.status == ToolStatus.NO_RESULTS
        assert "No emails found" in result.error

    def test_execute_empty_query(self, tool):
        """Test with empty query."""
        result = tool.execute(query="")

        assert result.success is False
        assert "empty" in result.error.lower()

    def test_execute_whitespace_query(self, tool):
        """Test with whitespace-only query."""
        result = tool.execute(query="   ")

        assert result.success is False
        assert "empty" in result.error.lower()

    def test_build_query_from_email(self, tool):
        """Test query builder with from email."""
        query = tool.build_query(from_email="john@example.com")
        assert query == "from:john@example.com"

    def test_build_query_multiple_params(self, tool):
        """Test query builder with multiple parameters."""
        query = tool.build_query(
            from_email="john@example.com",
            subject="proposal",
            after="2026/01/01",
        )

        assert "from:john@example.com" in query
        assert "subject:proposal" in query
        assert "after:2026/01/01" in query

    def test_build_query_with_attachment(self, tool):
        """Test query builder with attachment filter."""
        query = tool.build_query(has_attachment=True)
        assert "has:attachment" in query

    def test_build_query_unread(self, tool):
        """Test query builder with unread filter."""
        query = tool.build_query(is_unread=True)
        assert "is:unread" in query

    def test_build_query_read(self, tool):
        """Test query builder with read filter."""
        query = tool.build_query(is_unread=False)
        assert "is:read" in query

    def test_parse_email_date_valid(self, tool):
        """Test parsing valid email date."""
        result = tool._parse_email_date("Mon, 15 Jan 2026 10:30:00 +0000")

        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_email_date_with_timezone_abbrev(self, tool):
        """Test parsing date with timezone abbreviation."""
        result = tool._parse_email_date("Mon, 15 Jan 2026 10:30:00 -0800 (PST)")

        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_email_date_empty(self, tool):
        """Test parsing empty date returns now."""
        result = tool._parse_email_date("")

        # Should return current datetime
        assert result.date() == datetime.now().date()

    def test_parse_email_date_invalid(self, tool):
        """Test parsing invalid date returns now."""
        result = tool._parse_email_date("not a valid date")

        # Should return current datetime
        assert result.date() == datetime.now().date()

    def test_get_email_summary_success(self, tool, mock_gmail_service):
        """Test fetching email summary."""
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg123",
            "threadId": "thread456",
            "snippet": "Email snippet here",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "John Doe <john@example.com>"},
                    {"name": "Date", "value": "Mon, 15 Jan 2026 10:00:00 +0000"},
                ]
            },
        }

        result = tool._get_email_summary("msg123")

        assert result is not None
        assert result.message_id == "msg123"
        assert result.subject == "Test Subject"
        assert "john@example.com" in result.sender

    def test_max_results_parameter(self, tool, mock_gmail_service):
        """Test max_results limits results."""
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(10)],
            "resultSizeEstimate": 10,
        }
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg1",
            "threadId": "t1",
            "snippet": "...",
            "payload": {"headers": []},
        }

        # Call with max_results=3
        tool.execute(query="test", max_results=3)

        # Verify list was called with maxResults=3
        mock_gmail_service.users().messages().list.assert_called()
        call_kwargs = mock_gmail_service.users().messages().list.call_args[1]
        assert call_kwargs["maxResults"] == 3
