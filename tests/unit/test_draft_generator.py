"""Unit tests for draft generation service."""

from unittest.mock import MagicMock, patch

import pytest


class TestDraftGenerator:
    """Tests for DraftGenerator class."""

    @patch("email_agent.services.draft_generator.tone_detector")
    @patch("email_agent.services.draft_generator.ChatOpenAI")
    @patch("email_agent.services.draft_generator.settings")
    def test_generate_formal_draft(
        self, mock_settings, mock_llm_class, mock_tone_detector, formal_thread
    ):
        """Test generating a formal draft reply."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.temperature = 0.7
        mock_settings.max_tokens = 500

        mock_tone_detector.detect_tone.return_value = ("formal", 0.9)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """Dear John,

Thank you for your email. Thursday at 2:00 PM works well for me. I look forward to discussing the Q4 budget allocations.

Best regards"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.draft_generator import DraftGenerator

        generator = DraftGenerator()
        draft, tone, confidence = generator.generate_draft(
            thread=formal_thread,
            user_email="user@example.com",
            subject="Q4 Budget Review Meeting",
        )

        assert "Thank you" in draft
        assert tone == "formal"
        assert confidence == 0.9
        mock_tone_detector.detect_tone.assert_called_once_with(formal_thread)

    @patch("email_agent.services.draft_generator.tone_detector")
    @patch("email_agent.services.draft_generator.ChatOpenAI")
    @patch("email_agent.services.draft_generator.settings")
    def test_generate_casual_draft(
        self, mock_settings, mock_llm_class, mock_tone_detector, casual_thread
    ):
        """Test generating a casual draft reply."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.temperature = 0.7
        mock_settings.max_tokens = 500

        mock_tone_detector.detect_tone.return_value = ("casual", 0.85)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """Hey Mike!

Sure, I've got some time this afternoon. Give me a call whenever works for you!

Cheers"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.draft_generator import DraftGenerator

        generator = DraftGenerator()
        draft, tone, confidence = generator.generate_draft(
            thread=casual_thread,
            user_email="user@example.com",
            subject="Quick sync?",
        )

        assert "Hey" in draft or "Sure" in draft
        assert tone == "casual"
        assert confidence == 0.85

    @patch("email_agent.services.draft_generator.tone_detector")
    @patch("email_agent.services.draft_generator.ChatOpenAI")
    @patch("email_agent.services.draft_generator.settings")
    def test_draft_strips_whitespace(
        self, mock_settings, mock_llm_class, mock_tone_detector, formal_thread
    ):
        """Test that generated draft has whitespace stripped."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.temperature = 0.7
        mock_settings.max_tokens = 500

        mock_tone_detector.detect_tone.return_value = ("formal", 0.9)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "   \n\nDraft content here\n\n   "
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.draft_generator import DraftGenerator

        generator = DraftGenerator()
        draft, _, _ = generator.generate_draft(
            thread=formal_thread,
            user_email="user@example.com",
            subject="Test",
        )

        assert draft == "Draft content here"
        assert not draft.startswith(" ")
        assert not draft.endswith(" ")

    @patch("email_agent.services.draft_generator.tone_detector")
    @patch("email_agent.services.draft_generator.ChatOpenAI")
    @patch("email_agent.services.draft_generator.settings")
    def test_multi_message_thread_draft(
        self, mock_settings, mock_llm_class, mock_tone_detector, multi_message_thread
    ):
        """Test generating draft for multi-message thread."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.temperature = 0.7
        mock_settings.max_tokens = 500

        mock_tone_detector.detect_tone.return_value = ("casual", 0.78)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """Hi Sarah,

Monday works great! Let's move our call to then. Looking forward to sharing the preview on Wednesday.

Best"""
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.draft_generator import DraftGenerator

        generator = DraftGenerator()
        draft, tone, confidence = generator.generate_draft(
            thread=multi_message_thread,
            user_email="user@example.com",
            subject="Re: Project Phoenix Update",
        )

        assert draft is not None
        assert len(draft) > 0
        assert tone == "casual"

    @patch("email_agent.services.draft_generator.tone_detector")
    @patch("email_agent.services.draft_generator.ChatOpenAI")
    @patch("email_agent.services.draft_generator.settings")
    def test_returns_tuple_of_three(
        self, mock_settings, mock_llm_class, mock_tone_detector, formal_thread
    ):
        """Test that generate_draft returns a tuple of (draft, tone, confidence)."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.temperature = 0.7
        mock_settings.max_tokens = 500

        mock_tone_detector.detect_tone.return_value = ("formal", 0.88)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Draft content"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.draft_generator import DraftGenerator

        generator = DraftGenerator()
        result = generator.generate_draft(
            thread=formal_thread,
            user_email="user@example.com",
            subject="Test",
        )

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], str)  # draft
        assert isinstance(result[1], str)  # tone
        assert isinstance(result[2], float)  # confidence
