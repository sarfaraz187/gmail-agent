"""Tests for webhook endpoints."""

import base64
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestWebhookGmail:
    """Tests for POST /webhook/gmail endpoint."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for tests."""
        with patch("email_agent.api.webhook.settings") as mock:
            mock.label_agent_respond = "Agent Respond"
            mock.label_agent_done = "Agent Done"
            mock.label_agent_pending = "Agent Pending"
            yield mock

    @pytest.fixture
    def mock_dependencies(self, mock_settings):
        """Mock all external dependencies."""
        # Mock at both webhook and node levels since graph nodes import directly
        with patch("email_agent.api.webhook.label_manager") as mock_labels, \
             patch("email_agent.api.webhook.gmail_client") as mock_gmail, \
             patch("email_agent.api.webhook.history_tracker") as mock_history, \
             patch("email_agent.api.webhook.watch_service") as mock_watch, \
             patch("email_agent.api.webhook.invoke_graph") as mock_invoke_graph, \
             patch("email_agent.agent.nodes.notify.label_manager", mock_labels), \
             patch("email_agent.agent.nodes.send.label_manager", mock_labels), \
             patch("email_agent.agent.nodes.send.gmail_client", mock_gmail):
            # Make invoke_graph return a state that indicates pending
            mock_invoke_graph.return_value = {"outcome": "pending"}
            yield {
                "label_manager": mock_labels,
                "gmail_client": mock_gmail,
                "history_tracker": mock_history,
                "watch_service": mock_watch,
                "invoke_graph": mock_invoke_graph,
            }

    @pytest.fixture
    def client(self, mock_dependencies):
        """Create test client with mocked dependencies."""
        # Import after mocking to avoid initialization issues
        with patch("email_agent.config.settings") as mock_config:
            mock_config.openai_api_key = "test-key"
            mock_config.app_name = "Test App"
            mock_config.app_version = "0.0.1"
            mock_config.debug = False
            mock_config.label_agent_respond = "Agent Respond"
            mock_config.label_agent_done = "Agent Done"
            mock_config.label_agent_pending = "Agent Pending"

            from email_agent.main import app
            return TestClient(app)

    def _create_pubsub_request(self, email_address: str, history_id: int) -> dict:
        """Helper to create a Pub/Sub push request."""
        gmail_data = {
            "emailAddress": email_address,
            "historyId": history_id,
        }
        encoded_data = base64.urlsafe_b64encode(
            json.dumps(gmail_data).encode()
        ).decode()

        return {
            "message": {
                "data": encoded_data,
                "messageId": "test-message-123",
                "publishTime": "2025-01-11T10:00:00Z",
            },
            "subscription": "projects/test/subscriptions/gmail-agent-sub",
        }

    def test_webhook_first_run_initializes(self, client, mock_dependencies):
        """Test that first run initializes history ID."""
        mock_dependencies["label_manager"].get_label_id.return_value = "Label_123"
        mock_dependencies["history_tracker"].get_last_history_id.return_value = None

        request = self._create_pubsub_request("test@gmail.com", 12345)
        response = client.post("/webhook/gmail", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initialized"
        mock_dependencies["history_tracker"].update_history_id.assert_called_with(12345)

    def test_webhook_processes_new_messages(self, client, mock_dependencies):
        """Test processing new messages from history."""
        # Setup mocks
        mock_dependencies["label_manager"].get_label_id.return_value = "Label_123"
        mock_dependencies["history_tracker"].get_last_history_id.return_value = 12340

        # Mock history with one new message
        mock_record = MagicMock()
        mock_record.messages_added = [{"id": "msg1", "threadId": "thread1"}]
        mock_dependencies["gmail_client"].get_history.return_value = [mock_record]

        # Mock label checks (not already processed)
        mock_dependencies["label_manager"].has_label.return_value = False

        # Mock thread fetch with complete EmailData-like object
        mock_email = MagicMock()
        mock_email.message_id = "msg1"
        mock_email.thread_id = "thread1"
        mock_email.from_email = "john@example.com"
        mock_email.from_name = "John"
        mock_email.to_email = "test@gmail.com"
        mock_email.subject = "Test Subject"
        mock_email.body = "Test body"
        mock_email.snippet = "Test snippet"
        mock_email.date = "2025-01-11"
        mock_email.labels = ["INBOX"]
        mock_email.rfc_message_id = "<msg1@example.com>"
        mock_email.in_reply_to = None
        mock_email.references = None
        mock_dependencies["gmail_client"].get_thread.return_value = [mock_email]
        mock_dependencies["gmail_client"].should_skip_sender.return_value = False
        mock_dependencies["gmail_client"].is_auto_reply.return_value = False

        request = self._create_pubsub_request("test@gmail.com", 12350)
        response = client.post("/webhook/gmail", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1
        assert data["skipped"] == 0

        # Verify the agent graph was invoked with the message
        mock_dependencies["invoke_graph"].assert_called_once()

    def test_webhook_skips_already_processed(self, client, mock_dependencies):
        """Test that already processed messages are skipped."""
        mock_dependencies["label_manager"].get_label_id.return_value = "Label_123"
        mock_dependencies["history_tracker"].get_last_history_id.return_value = 12340

        mock_record = MagicMock()
        mock_record.messages_added = [{"id": "msg1", "threadId": "thread1"}]
        mock_dependencies["gmail_client"].get_history.return_value = [mock_record]

        # Message already has "Agent Done" label
        mock_dependencies["label_manager"].has_label.side_effect = (
            lambda msg_id, label: label == "Agent Done"
        )

        request = self._create_pubsub_request("test@gmail.com", 12350)
        response = client.post("/webhook/gmail", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0
        assert data["skipped"] == 1

    def test_webhook_skips_noreply_sender(self, client, mock_dependencies):
        """Test that noreply senders are skipped."""
        mock_dependencies["label_manager"].get_label_id.return_value = "Label_123"
        mock_dependencies["history_tracker"].get_last_history_id.return_value = 12340

        mock_record = MagicMock()
        mock_record.messages_added = [{"id": "msg1", "threadId": "thread1"}]
        mock_dependencies["gmail_client"].get_history.return_value = [mock_record]

        mock_dependencies["label_manager"].has_label.return_value = False

        mock_email = MagicMock()
        mock_email.from_email = "noreply@example.com"
        mock_dependencies["gmail_client"].get_thread.return_value = [mock_email]
        mock_dependencies["gmail_client"].should_skip_sender.return_value = True

        request = self._create_pubsub_request("test@gmail.com", 12350)
        response = client.post("/webhook/gmail", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1

    def test_webhook_invalid_base64_returns_error(self, client, mock_dependencies):
        """Test that invalid base64 data is handled gracefully."""
        request = {
            "message": {
                "data": "not-valid-base64!!!",
                "messageId": "test-123",
                "publishTime": "2025-01-11T10:00:00Z",
            },
            "subscription": "projects/test/subscriptions/gmail-agent-sub",
        }

        response = client.post("/webhook/gmail", json=request)

        # Should still return 200 to acknowledge (avoid infinite retries)
        assert response.status_code == 200
        assert response.json()["status"] == "error"


class TestRenewWatch:
    """Tests for POST /renew-watch endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        with patch("email_agent.config.settings") as mock_config, \
             patch("email_agent.api.webhook.label_manager") as mock_labels, \
             patch("email_agent.api.webhook.watch_service") as mock_watch:

            mock_config.openai_api_key = "test-key"
            mock_config.app_name = "Test App"
            mock_config.app_version = "0.0.1"
            mock_config.debug = False

            from datetime import datetime, timezone
            mock_watch.renew_watch.return_value = MagicMock(
                history_id=12345,
                expiration=datetime(2025, 1, 18, 10, 0, 0, tzinfo=timezone.utc),
            )

            from email_agent.main import app
            yield TestClient(app)

    def test_renew_watch_success(self, client):
        """Test successful watch renewal."""
        response = client.post("/renew-watch")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "renewed" in data["message"].lower()
        assert data["history_id"] == 12345


class TestWatchStatus:
    """Tests for GET /watch-status endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked dependencies."""
        with patch("email_agent.config.settings") as mock_config, \
             patch("email_agent.api.webhook.watch_service") as mock_watch, \
             patch("email_agent.api.webhook.settings") as mock_webhook_settings:

            mock_config.openai_api_key = "test-key"
            mock_config.app_name = "Test App"
            mock_config.app_version = "0.0.1"
            mock_config.debug = False

            mock_webhook_settings.label_agent_respond = "Agent Respond"
            mock_webhook_settings.pubsub_topic = "gmail-agent"

            from datetime import datetime, timezone
            mock_watch.get_watch_expiration.return_value = datetime(
                2025, 1, 18, 10, 0, 0, tzinfo=timezone.utc
            )

            from email_agent.main import app
            yield TestClient(app)

    def test_watch_status_active(self, client):
        """Test getting status when watch is active."""
        response = client.get("/watch-status")

        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        assert data["label_name"] == "Agent Respond"
        assert data["pubsub_topic"] == "gmail-agent"


class TestPubSubMessageDecoding:
    """Tests for Pub/Sub message decoding."""

    def test_decode_valid_message(self):
        """Test decoding a valid Pub/Sub message."""
        from email_agent.api.webhook import _decode_pubsub_message

        gmail_data = {"emailAddress": "test@gmail.com", "historyId": 12345}
        encoded = base64.urlsafe_b64encode(json.dumps(gmail_data).encode()).decode()

        result = _decode_pubsub_message(encoded)

        assert result.emailAddress == "test@gmail.com"
        assert result.historyId == 12345

    def test_decode_invalid_base64(self):
        """Test that invalid base64 raises ValueError."""
        from email_agent.api.webhook import _decode_pubsub_message

        with pytest.raises(ValueError):
            _decode_pubsub_message("not-valid-base64!!!")

    def test_decode_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        from email_agent.api.webhook import _decode_pubsub_message

        encoded = base64.urlsafe_b64encode(b"not json").decode()

        with pytest.raises(ValueError):
            _decode_pubsub_message(encoded)
