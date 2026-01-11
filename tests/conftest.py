"""Shared test fixtures and configuration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_emails() -> dict:
    """Load sample email fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_emails.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def formal_thread(sample_emails: dict) -> list[dict]:
    """Single formal email thread."""
    return sample_emails["formal_thread"]


@pytest.fixture
def casual_thread(sample_emails: dict) -> list[dict]:
    """Single casual email thread."""
    return sample_emails["casual_thread"]


@pytest.fixture
def multi_message_thread(sample_emails: dict) -> list[dict]:
    """Multi-message email thread."""
    return sample_emails["multi_message_thread"]


@pytest.fixture
def decision_required_thread(sample_emails: dict) -> list[dict]:
    """Thread requiring user decision."""
    return sample_emails["decision_required_thread"]


@pytest.fixture
def meeting_request_thread(sample_emails: dict) -> list[dict]:
    """Simple meeting request thread."""
    return sample_emails["meeting_request_thread"]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI LLM response."""
    mock_response = MagicMock()
    mock_response.content = '{"tone": "formal", "confidence": 0.85}'
    return mock_response


@pytest.fixture
def mock_draft_response():
    """Mock draft generation response."""
    mock_response = MagicMock()
    mock_response.content = """Dear John,

Thank you for your email. Thursday at 2:00 PM works well for me. I look forward to discussing the Q4 budget allocations.

Best regards"""
    return mock_response


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    with patch("email_agent.config.settings") as mock:
        mock.openai_api_key = "test-api-key"
        mock.openai_model = "gpt-4o"
        mock.temperature = 0.7
        mock.max_tokens = 500
        mock.app_name = "Gmail AI Agent"
        mock.app_version = "0.1.0"
        mock.debug = False
        yield mock


@pytest.fixture
def test_client(mock_settings):
    """FastAPI test client with mocked settings."""
    from email_agent.main import app

    with TestClient(app) as client:
        yield client
