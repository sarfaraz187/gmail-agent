"""Tests for the notify node."""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.notify import notify_node
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


class TestNotifyNode:
    """Tests for notify_node function."""

    @pytest.fixture
    def mock_label_manager(self):
        """Mock label manager."""
        with patch("email_agent.agent.nodes.notify.label_manager") as mock:
            yield mock

    @pytest.fixture
    def sample_state(self):
        """Create sample state."""
        latest = MockEmailData()
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
            "classification": None,
        }

    def test_notify_success(self, mock_label_manager, sample_state):
        """Test successful notification (mark as pending)."""
        result = notify_node(sample_state)

        assert result["outcome"] == "pending"
        assert result["error_message"] is None
        mock_label_manager.transition_to_pending.assert_called_once_with("msg123")

    def test_notify_with_classification(self, mock_label_manager, sample_state):
        """Test notify with classification info."""
        classification = MagicMock()
        classification.decision = DecisionType.NEEDS_CHOICE
        classification.email_type = EmailType.UNKNOWN
        classification.reason = "Budget question needs user input"
        sample_state["classification"] = classification

        result = notify_node(sample_state)

        assert result["outcome"] == "pending"
        mock_label_manager.transition_to_pending.assert_called_once()

    def test_notify_without_classification(self, mock_label_manager, sample_state):
        """Test notify when classification is None."""
        sample_state["classification"] = None

        result = notify_node(sample_state)

        assert result["outcome"] == "pending"
        mock_label_manager.transition_to_pending.assert_called_once()

    def test_notify_failure(self, mock_label_manager, sample_state):
        """Test handling of label transition failure."""
        mock_label_manager.transition_to_pending.side_effect = Exception("Gmail API error")

        result = notify_node(sample_state)

        assert result["outcome"] == "error"
        assert "Gmail API error" in result["error_message"]

    def test_notify_needs_approval(self, mock_label_manager, sample_state):
        """Test notify for NEEDS_APPROVAL decision."""
        classification = MagicMock()
        classification.decision = DecisionType.NEEDS_APPROVAL
        classification.email_type = EmailType.INFO_REQUEST
        classification.reason = "Large contract requires approval"
        sample_state["classification"] = classification

        result = notify_node(sample_state)

        assert result["outcome"] == "pending"

    def test_notify_needs_input(self, mock_label_manager, sample_state):
        """Test notify for NEEDS_INPUT decision."""
        classification = MagicMock()
        classification.decision = DecisionType.NEEDS_INPUT
        classification.email_type = EmailType.UNKNOWN
        classification.reason = "Missing information to respond"
        sample_state["classification"] = classification

        result = notify_node(sample_state)

        assert result["outcome"] == "pending"
