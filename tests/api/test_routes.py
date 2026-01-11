"""API endpoint tests."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @patch("email_agent.config.settings")
    def test_health_check_returns_200(self, mock_settings):
        """Test that health check returns 200 OK."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200

    @patch("email_agent.config.settings")
    def test_health_check_response_format(self, mock_settings):
        """Test health check response contains expected fields."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.get("/health")

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] == "healthy"


class TestGenerateDraftEndpoint:
    """Tests for /generate-draft endpoint."""

    @patch("email_agent.api.routes.draft_generator")
    @patch("email_agent.config.settings")
    def test_generate_draft_success(self, mock_settings, mock_generator):
        """Test successful draft generation."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        mock_generator.generate_draft.return_value = (
            "Thank you for your email. I will review and respond shortly.",
            "formal",
            0.88,
        )

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.post(
                "/generate-draft",
                json={
                    "thread": [
                        {
                            "from": "sender@example.com",
                            "to": "user@example.com",
                            "date": "2025-01-10T10:00:00Z",
                            "subject": "Test Subject",
                            "body": "Hello, this is a test email.",
                        }
                    ],
                    "user_email": "user@example.com",
                    "subject": "Test Subject",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "draft" in data
        assert "detected_tone" in data
        assert "confidence" in data
        assert data["detected_tone"] == "formal"
        assert data["confidence"] == 0.88

    @patch("email_agent.api.routes.draft_generator")
    @patch("email_agent.config.settings")
    def test_generate_draft_multi_message_thread(self, mock_settings, mock_generator):
        """Test draft generation with multi-message thread."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        mock_generator.generate_draft.return_value = (
            "Sounds good! Monday works for me.",
            "casual",
            0.75,
        )

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.post(
                "/generate-draft",
                json={
                    "thread": [
                        {
                            "from": "sender@example.com",
                            "to": "user@example.com",
                            "date": "2025-01-08T10:00:00Z",
                            "subject": "Project Update",
                            "body": "Hey, how's the project going?",
                        },
                        {
                            "from": "user@example.com",
                            "to": "sender@example.com",
                            "date": "2025-01-09T14:00:00Z",
                            "subject": "Re: Project Update",
                            "body": "Going well! Should be done by Friday.",
                        },
                        {
                            "from": "sender@example.com",
                            "to": "user@example.com",
                            "date": "2025-01-10T09:00:00Z",
                            "subject": "Re: Project Update",
                            "body": "Great! Can we meet Monday to review?",
                        },
                    ],
                    "user_email": "user@example.com",
                    "subject": "Re: Project Update",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["detected_tone"] == "casual"

    @patch("email_agent.config.settings")
    def test_generate_draft_missing_required_field(self, mock_settings):
        """Test that missing required fields return 422."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.post(
                "/generate-draft",
                json={
                    "thread": [],
                    # Missing user_email and subject
                },
            )

        assert response.status_code == 422

    @patch("email_agent.config.settings")
    def test_generate_draft_invalid_email_message(self, mock_settings):
        """Test that invalid email message format returns 422."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.post(
                "/generate-draft",
                json={
                    "thread": [
                        {
                            "from": "sender@example.com",
                            # Missing required fields: to, date, subject, body
                        }
                    ],
                    "user_email": "user@example.com",
                    "subject": "Test",
                },
            )

        assert response.status_code == 422

    @patch("email_agent.api.routes.draft_generator")
    @patch("email_agent.config.settings")
    def test_generate_draft_internal_error(self, mock_settings, mock_generator):
        """Test that internal errors return 500."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.app_name = "Gmail AI Agent"
        mock_settings.app_version = "0.1.0"
        mock_settings.debug = False

        mock_generator.generate_draft.side_effect = Exception("LLM API Error")

        from email_agent.main import app

        with TestClient(app) as client:
            response = client.post(
                "/generate-draft",
                json={
                    "thread": [
                        {
                            "from": "sender@example.com",
                            "to": "user@example.com",
                            "date": "2025-01-10T10:00:00Z",
                            "subject": "Test",
                            "body": "Test body",
                        }
                    ],
                    "user_email": "user@example.com",
                    "subject": "Test",
                },
            )

        assert response.status_code == 500
        assert "Failed to generate draft" in response.json()["detail"]


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_email_message_schema_valid(self):
        """Test valid EmailMessage schema."""
        from email_agent.api.schemas import EmailMessage

        msg = EmailMessage(
            **{
                "from": "sender@example.com",
                "to": "recipient@example.com",
                "date": "2025-01-10T10:00:00Z",
                "subject": "Test Subject",
                "body": "Test body content",
            }
        )

        assert msg.from_ == "sender@example.com"
        assert msg.to == "recipient@example.com"
        assert msg.subject == "Test Subject"

    def test_generate_draft_response_confidence_bounds(self):
        """Test that confidence must be between 0 and 1."""
        from pydantic import ValidationError

        from email_agent.api.schemas import GenerateDraftResponse

        # Valid confidence
        response = GenerateDraftResponse(
            draft="Test draft",
            detected_tone="formal",
            confidence=0.85,
        )
        assert response.confidence == 0.85

        # Invalid confidence > 1
        with pytest.raises(ValidationError):
            GenerateDraftResponse(
                draft="Test draft",
                detected_tone="formal",
                confidence=1.5,
            )

        # Invalid confidence < 0
        with pytest.raises(ValidationError):
            GenerateDraftResponse(
                draft="Test draft",
                detected_tone="formal",
                confidence=-0.1,
            )
