"""Unit tests for tone detection service."""

from unittest.mock import MagicMock, patch

import pytest


class TestToneDetector:
    """Tests for ToneDetector class."""

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_detect_formal_tone(self, mock_settings, mock_llm_class, formal_thread):
        """Test detection of formal tone."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "formal", "confidence": 0.92}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(formal_thread)

        assert tone == "formal"
        assert confidence == 0.92
        mock_llm.invoke.assert_called_once()

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_detect_casual_tone(self, mock_settings, mock_llm_class, casual_thread):
        """Test detection of casual tone."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "casual", "confidence": 0.88}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(casual_thread)

        assert tone == "casual"
        assert confidence == 0.88

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_invalid_tone_defaults_to_formal(self, mock_settings, mock_llm_class, formal_thread):
        """Test that invalid tone values default to formal."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "aggressive", "confidence": 0.75}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(formal_thread)

        assert tone == "formal"
        assert confidence == 0.75

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_confidence_clamped_to_valid_range(self, mock_settings, mock_llm_class, formal_thread):
        """Test that confidence is clamped between 0 and 1."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "formal", "confidence": 1.5}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(formal_thread)

        assert confidence == 1.0

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_negative_confidence_clamped_to_zero(self, mock_settings, mock_llm_class, formal_thread):
        """Test that negative confidence is clamped to 0."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "casual", "confidence": -0.5}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(formal_thread)

        assert confidence == 0.0

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_json_parse_error_returns_default(self, mock_settings, mock_llm_class, formal_thread):
        """Test that JSON parse errors return default values."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(formal_thread)

        assert tone == "formal"
        assert confidence == 0.5

    @patch("email_agent.services.tone_detector.ChatOpenAI")
    @patch("email_agent.services.tone_detector.settings")
    def test_multi_message_thread(self, mock_settings, mock_llm_class, multi_message_thread):
        """Test tone detection on multi-message thread."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tone": "casual", "confidence": 0.78}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.tone_detector import ToneDetector

        detector = ToneDetector()
        tone, confidence = detector.detect_tone(multi_message_thread)

        assert tone == "casual"
        assert confidence == 0.78
        mock_llm.invoke.assert_called_once()


class TestFormatThreadForPrompt:
    """Tests for format_thread_for_prompt helper."""

    def test_single_message_format(self, formal_thread):
        """Test formatting single message thread."""
        from email_agent.prompts.templates import format_thread_for_prompt

        result = format_thread_for_prompt(formal_thread)

        assert "Email 1" in result
        assert "john.smith@company.com" in result
        assert "Q4 Budget Review Meeting" in result
        assert "Dear Team" in result

    def test_multi_message_format(self, multi_message_thread):
        """Test formatting multi-message thread."""
        from email_agent.prompts.templates import format_thread_for_prompt

        result = format_thread_for_prompt(multi_message_thread)

        assert "Email 1" in result
        assert "Email 2" in result
        assert "Email 3" in result
        assert "sarah@client.com" in result
        assert "Project Phoenix" in result

    def test_handles_missing_fields(self):
        """Test handling of emails with missing fields."""
        from email_agent.prompts.templates import format_thread_for_prompt

        incomplete_thread = [{"body": "Just a body"}]
        result = format_thread_for_prompt(incomplete_thread)

        assert "Unknown" in result
        assert "Just a body" in result
