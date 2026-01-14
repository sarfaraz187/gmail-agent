"""Tests for the classify node."""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.classify import classify_node
from email_agent.agent.classifier import DecisionType, EmailType


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


class TestClassifyNode:
    """Tests for classify_node function."""

    @pytest.fixture
    def mock_classifier(self):
        """Mock email classifier."""
        with patch("email_agent.agent.nodes.classify.email_classifier") as mock:
            yield mock

    @pytest.fixture
    def sample_state(self):
        """Create a sample agent state."""
        latest = MockEmailData(
            subject="Can we meet Thursday?",
            body="Hi, can we schedule a meeting for Thursday afternoon?"
        )
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
        }

    def test_classify_auto_respond(self, mock_classifier, sample_state):
        """Test classification as AUTO_RESPOND."""
        mock_result = MagicMock()
        mock_result.decision = DecisionType.AUTO_RESPOND
        mock_result.email_type = EmailType.SCHEDULING_REQUEST
        mock_result.confidence = 0.95
        mock_result.reason = "Simple meeting request"
        mock_classifier.classify.return_value = mock_result
        mock_classifier.detect_language.return_value = "en"

        result = classify_node(sample_state)

        assert result["classification"] == mock_result
        assert result["detected_language"] == "en"
        mock_classifier.classify.assert_called_once()

    def test_classify_needs_choice(self, mock_classifier, sample_state):
        """Test classification as NEEDS_CHOICE."""
        mock_result = MagicMock()
        mock_result.decision = DecisionType.NEEDS_CHOICE
        mock_result.email_type = EmailType.UNKNOWN
        mock_result.confidence = 0.8
        mock_result.reason = "Budget question needs user input"
        mock_classifier.classify.return_value = mock_result
        mock_classifier.detect_language.return_value = "en"

        result = classify_node(sample_state)

        assert result["classification"].decision == DecisionType.NEEDS_CHOICE

    def test_classify_with_thread_context(self, mock_classifier):
        """Test that thread context is passed correctly."""
        prev_email = MockEmailData(body="Previous email content")
        latest = MockEmailData(body="Latest email content")

        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [prev_email, latest],
            "latest_email": latest,
        }

        mock_result = MagicMock()
        mock_result.decision = DecisionType.AUTO_RESPOND
        mock_result.email_type = EmailType.SIMPLE_ACKNOWLEDGMENT
        mock_result.confidence = 0.9
        mock_classifier.classify.return_value = mock_result
        mock_classifier.detect_language.return_value = "en"

        classify_node(state)

        # Verify thread context was passed (excluding latest email)
        call_args = mock_classifier.classify.call_args
        assert call_args.kwargs["thread_context"] == ["Previous email content"]

    def test_classify_detects_language(self, mock_classifier, sample_state):
        """Test language detection."""
        mock_result = MagicMock()
        mock_result.decision = DecisionType.AUTO_RESPOND
        mock_result.email_type = EmailType.SIMPLE_ACKNOWLEDGMENT
        mock_result.confidence = 0.9
        mock_classifier.classify.return_value = mock_result
        mock_classifier.detect_language.return_value = "es"

        result = classify_node(sample_state)

        assert result["detected_language"] == "es"
        mock_classifier.detect_language.assert_called_once()

    def test_classify_empty_thread_context(self, mock_classifier):
        """Test with single email (no previous context)."""
        latest = MockEmailData()

        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
        }

        mock_result = MagicMock()
        mock_result.decision = DecisionType.AUTO_RESPOND
        mock_result.email_type = EmailType.SIMPLE_ACKNOWLEDGMENT
        mock_result.confidence = 0.9
        mock_classifier.classify.return_value = mock_result
        mock_classifier.detect_language.return_value = "en"

        classify_node(state)

        call_args = mock_classifier.classify.call_args
        assert call_args.kwargs["thread_context"] == []
