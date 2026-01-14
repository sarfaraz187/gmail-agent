"""Tests for the send node."""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent.nodes.send import send_node, _extract_name_from_email


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


class TestSendNode:
    """Tests for send_node function."""

    @pytest.fixture
    def mock_gmail_client(self):
        """Mock Gmail client."""
        with patch("email_agent.agent.nodes.send.gmail_client") as mock:
            yield mock

    @pytest.fixture
    def mock_label_manager(self):
        """Mock label manager."""
        with patch("email_agent.agent.nodes.send.label_manager") as mock:
            yield mock

    @pytest.fixture
    def mock_style_learner(self):
        """Mock style learner (used in _trigger_learning)."""
        with patch("email_agent.services.style_learner.style_learner") as mock:
            yield mock

    @pytest.fixture
    def sample_state(self):
        """Create sample state with draft ready."""
        latest = MockEmailData(
            from_email="John Doe <john@example.com>",
            rfc_message_id="<original-123@example.com>",
            references=None
        )
        return {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
            "draft_body": "Thank you for your email.",
            "html_body": "<p>Thank you for your email.</p>",
            "plain_body": "Thank you for your email.",
        }

    def test_send_success(
        self, mock_gmail_client, mock_label_manager, mock_style_learner, sample_state
    ):
        """Test successful email send."""
        result = send_node(sample_state)

        assert result["outcome"] == "sent"
        assert result["error_message"] is None
        mock_gmail_client.send_reply.assert_called_once()
        mock_label_manager.transition_to_done.assert_called_once_with("msg123")

    def test_send_includes_threading_headers(
        self, mock_gmail_client, mock_label_manager, mock_style_learner, sample_state
    ):
        """Test that proper threading headers are included."""
        send_node(sample_state)

        call_args = mock_gmail_client.send_reply.call_args
        assert call_args.kwargs["in_reply_to"] == "<original-123@example.com>"
        assert call_args.kwargs["thread_id"] == "thread123"

    def test_send_builds_references_header(
        self, mock_gmail_client, mock_label_manager, mock_style_learner, sample_state
    ):
        """Test building References header from existing references."""
        sample_state["latest_email"].references = "<prev-1@example.com> <prev-2@example.com>"

        send_node(sample_state)

        call_args = mock_gmail_client.send_reply.call_args
        # References should include original references + message being replied to
        expected = "<prev-1@example.com> <prev-2@example.com> <original-123@example.com>"
        assert call_args.kwargs["references"] == expected

    def test_send_failure_marks_pending(
        self, mock_gmail_client, mock_label_manager, mock_style_learner, sample_state
    ):
        """Test that send failure marks email as pending."""
        mock_gmail_client.send_reply.side_effect = Exception("SMTP error")

        result = send_node(sample_state)

        assert result["outcome"] == "error"
        assert "SMTP error" in result["error_message"]
        mock_label_manager.transition_to_pending.assert_called_once_with("msg123")

    def test_send_failure_handles_label_error(
        self, mock_gmail_client, mock_label_manager, mock_style_learner, sample_state
    ):
        """Test handling when both send and label transition fail."""
        mock_gmail_client.send_reply.side_effect = Exception("SMTP error")
        mock_label_manager.transition_to_pending.side_effect = Exception("Label error")

        result = send_node(sample_state)

        # Should still return error outcome even if label transition fails
        assert result["outcome"] == "error"
        assert "SMTP error" in result["error_message"]

    def test_send_triggers_learning(
        self, mock_gmail_client, mock_label_manager, sample_state
    ):
        """Test that learning is triggered after successful send."""
        with patch("email_agent.agent.nodes.send._trigger_learning") as mock_trigger:
            send_node(sample_state)
            mock_trigger.assert_called_once()

    def test_send_learning_failure_doesnt_affect_outcome(
        self, mock_gmail_client, mock_label_manager, sample_state
    ):
        """Test that learning failure doesn't affect send outcome."""
        # Mock the style_learner that's imported inside _trigger_learning
        with patch("email_agent.services.style_learner.style_learner") as mock_learner:
            mock_learner.learn_from_sent_email.side_effect = Exception("Learning failed")
            # Should still succeed overall - learning is fire-and-forget
            result = send_node(sample_state)
            assert result["outcome"] == "sent"

    def test_send_without_rfc_message_id(
        self, mock_gmail_client, mock_label_manager, mock_style_learner
    ):
        """Test send when original email has no RFC Message-ID."""
        latest = MockEmailData(rfc_message_id=None, references=None)
        state = {
            "message_id": "msg123",
            "thread_id": "thread123",
            "thread_emails": [latest],
            "latest_email": latest,
            "draft_body": "Reply",
            "html_body": "<p>Reply</p>",
            "plain_body": "Reply",
        }

        send_node(state)

        call_args = mock_gmail_client.send_reply.call_args
        assert call_args.kwargs["in_reply_to"] is None


class TestExtractNameFromEmail:
    """Tests for _extract_name_from_email helper."""

    def test_extract_with_name(self):
        """Test extraction from 'Name <email>' format."""
        assert _extract_name_from_email("John Doe <john@example.com>") == "John Doe"

    def test_extract_plain_email(self):
        """Test plain email returns empty string."""
        assert _extract_name_from_email("john@example.com") == ""

    def test_extract_quoted_name(self):
        """Test quoted name format."""
        assert _extract_name_from_email('"Jane Smith" <jane@example.com>') == "Jane Smith"
