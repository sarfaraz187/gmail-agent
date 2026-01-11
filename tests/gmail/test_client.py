"""Tests for the Gmail client module."""

import pytest
from unittest.mock import patch, MagicMock

from email_agent.gmail.client import (
    GmailClient,
    EmailData,
    NEVER_RESPOND_PATTERNS,
    AUTO_REPLY_PATTERNS,
)


class TestShouldSkipSender:
    """Tests for noreply/automated sender detection."""

    @pytest.fixture
    def client(self):
        """Create a Gmail client without connecting to API."""
        with patch("email_agent.gmail.client.get_gmail_service"):
            return GmailClient()

    @pytest.mark.parametrize(
        "email,should_skip",
        [
            # Should skip (automated senders)
            ("noreply@example.com", True),
            ("no-reply@example.com", True),
            ("donotreply@company.com", True),
            ("do-not-reply@company.com", True),
            ("mailer-daemon@google.com", True),
            ("postmaster@gmail.com", True),
            ("notifications@github.com", True),
            ("notification@linkedin.com", True),
            ("alerts@aws.amazon.com", True),
            ("bounce@mail.example.com", True),
            ("automated@system.com", True),
            ("auto-reply@company.com", True),
            ("NOREPLY@EXAMPLE.COM", True),  # Case insensitive
            # Should NOT skip (real people)
            ("john@example.com", False),
            ("sarah.smith@company.com", False),
            ("support@company.com", False),
            ("info@business.com", False),
            ("contact@website.com", False),
            ("reply@company.com", False),  # Has 'reply' but not 'noreply'
        ],
    )
    def test_should_skip_sender(self, client, email, should_skip):
        """Test various email addresses for skip detection."""
        result = client.should_skip_sender(email)
        assert result == should_skip, f"Expected {should_skip} for {email}"


class TestIsAutoReply:
    """Tests for auto-reply detection (out of office, etc.)."""

    @pytest.fixture
    def client(self):
        """Create a Gmail client without connecting to API."""
        with patch("email_agent.gmail.client.get_gmail_service"):
            return GmailClient()

    @pytest.mark.parametrize(
        "subject,body,is_auto",
        [
            # Auto-replies
            ("Out of Office: Re: Meeting", "", True),
            ("Re: Question", "I am out of office until Monday", True),
            ("Automatic Reply: Your email", "", True),
            ("Auto-Reply: Received", "", True),
            ("RE: Project", "I am away from the office this week", True),
            ("Vacation", "I am on vacation until next month", True),
            ("Re: Urgent", "I am currently unavailable", True),
            ("OOO", "out-of-office automatic response", True),
            # NOT auto-replies
            ("Meeting Request", "Can we meet tomorrow?", False),
            ("Project Update", "Here's the latest status", False),
            ("Question about office supplies", "We need more paper", False),
            ("Re: Budget", "I approve the budget", False),
        ],
    )
    def test_is_auto_reply(self, client, subject, body, is_auto):
        """Test various emails for auto-reply detection."""
        result = client.is_auto_reply(subject, body)
        assert result == is_auto, f"Expected {is_auto} for subject='{subject}'"


class TestParseEmailAddress:
    """Tests for email address parsing."""

    @pytest.fixture
    def client(self):
        """Create a Gmail client without connecting to API."""
        with patch("email_agent.gmail.client.get_gmail_service"):
            return GmailClient()

    @pytest.mark.parametrize(
        "address,expected_name,expected_email",
        [
            # Standard formats
            ("John Smith <john@example.com>", "John Smith", "john@example.com"),
            ('"Jane Doe" <jane@company.com>', "Jane Doe", "jane@company.com"),
            ("john@example.com", "", "john@example.com"),
            ("<john@example.com>", "", "john@example.com"),
            # Edge cases
            ("  John  <john@example.com>  ", "John", "john@example.com"),
            ("Dr. Smith <dr.smith@hospital.com>", "Dr. Smith", "dr.smith@hospital.com"),
        ],
    )
    def test_parse_email_address(self, client, address, expected_name, expected_email):
        """Test parsing various email address formats."""
        name, email = client._parse_email_address(address)
        assert name == expected_name
        assert email == expected_email


class TestExtractBody:
    """Tests for email body extraction."""

    @pytest.fixture
    def client(self):
        """Create a Gmail client without connecting to API."""
        with patch("email_agent.gmail.client.get_gmail_service"):
            return GmailClient()

    def test_extract_simple_body(self, client):
        """Test extracting body from simple email."""
        import base64

        body_text = "Hello, this is the email body."
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()

        payload = {"body": {"data": encoded}}

        result = client._extract_body(payload)
        assert result == body_text

    def test_extract_multipart_body(self, client):
        """Test extracting body from multipart email."""
        import base64

        body_text = "Plain text content"
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()

        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}},
                {"mimeType": "text/html", "body": {"data": "htmlcontent"}},
            ]
        }

        result = client._extract_body(payload)
        assert result == body_text

    def test_extract_body_empty_payload(self, client):
        """Test extracting body from empty payload."""
        result = client._extract_body({})
        assert result == ""


class TestParseMessage:
    """Tests for full message parsing."""

    @pytest.fixture
    def client(self):
        """Create a Gmail client without connecting to API."""
        with patch("email_agent.gmail.client.get_gmail_service"):
            return GmailClient()

    def test_parse_message(self, client):
        """Test parsing a complete Gmail message."""
        import base64

        body_text = "Test email body"
        encoded_body = base64.urlsafe_b64encode(body_text.encode()).decode()

        message = {
            "id": "msg123",
            "threadId": "thread456",
            "snippet": "Test email...",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "John <john@example.com>"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 11 Jan 2025 10:00:00 +0000"},
                    {"name": "In-Reply-To", "value": "<original@message.id>"},
                ],
                "body": {"data": encoded_body},
            },
        }

        result = client._parse_message(message)

        assert isinstance(result, EmailData)
        assert result.message_id == "msg123"
        assert result.thread_id == "thread456"
        assert result.from_email == "john@example.com"
        assert result.from_name == "John"
        assert result.to_email == "me@example.com"
        assert result.subject == "Test Subject"
        assert result.body == body_text
        assert result.snippet == "Test email..."
        assert result.in_reply_to == "<original@message.id>"
        assert "INBOX" in result.labels
