"""Unit tests for style learner service."""

import json
import pytest
from unittest.mock import MagicMock, patch

from email_agent.storage.contact_memory import (
    ContactMemoryStore,
    ContactStyle,
)


class TestStyleAnalysis:
    """Tests for StyleAnalysis dataclass."""

    def test_style_analysis_creation(self):
        """Test creating a StyleAnalysis."""
        from email_agent.services.style_learner import StyleAnalysis

        analysis = StyleAnalysis(
            tone="casual",
            greeting_used="Hi John,",
            formality_score=0.3,
            response_length="short",
            topics_discussed=["project", "deadline"],
        )
        assert analysis.tone == "casual"
        assert analysis.greeting_used == "Hi John,"
        assert analysis.formality_score == 0.3
        assert analysis.response_length == "short"
        assert len(analysis.topics_discussed) == 2


class TestStyleLearnerAnalysis:
    """Tests for StyleLearner.analyze_sent_email."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        return {
            "tone": "casual",
            "greeting_used": "Hi John,",
            "formality_score": 0.3,
            "response_length": "short",
            "topics_discussed": ["project update", "deadline"],
        }

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_analyze_sent_email_success(
        self, mock_settings, mock_llm_class, mock_store, mock_llm_response
    ):
        """Test successful style analysis."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(mock_llm_response)
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner()
        result = learner.analyze_sent_email(
            sent_body="Hi John, Just wanted to follow up on the project.",
            recipient_email="john@example.com",
            recipient_name="John",
        )

        assert result.tone == "casual"
        assert result.greeting_used == "Hi John,"
        assert result.formality_score == 0.3
        assert result.response_length == "short"
        assert "project update" in result.topics_discussed

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_analyze_sent_email_with_thread_context(
        self, mock_settings, mock_llm_class, mock_store, mock_llm_response
    ):
        """Test analysis with thread context."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(mock_llm_response)
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner()
        learner.analyze_sent_email(
            sent_body="Thanks for the update!",
            recipient_email="john@example.com",
            thread_context=["Previous email 1", "Previous email 2"],
        )

        # Verify context was passed to LLM
        call_args = mock_llm.invoke.call_args[0][0][0].content
        assert "Previous email 1" in call_args
        assert "Previous email 2" in call_args

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_analyze_sent_email_json_error(
        self, mock_settings, mock_llm_class, mock_store
    ):
        """Test handling of JSON parse error."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "invalid json"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner()
        result = learner.analyze_sent_email(
            sent_body="Test email",
            recipient_email="test@example.com",
        )

        # Should return defaults
        assert result.tone == "formal"
        assert result.formality_score == 0.5
        assert result.response_length == "medium"

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_analyze_sent_email_limits_topics(
        self, mock_settings, mock_llm_class, mock_store
    ):
        """Test that topics are limited to 3."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        response_data = {
            "tone": "formal",
            "greeting_used": "",
            "formality_score": 0.7,
            "response_length": "medium",
            "topics_discussed": ["topic1", "topic2", "topic3", "topic4", "topic5"],
        }

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(response_data)
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner()
        result = learner.analyze_sent_email(
            sent_body="Test email",
            recipient_email="test@example.com",
        )

        assert len(result.topics_discussed) == 3


class TestStyleLearnerMerge:
    """Tests for StyleLearner.merge_style."""

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_merge_style_first_email(self, mock_settings, mock_llm_class, mock_store):
        """Test merging when no existing style."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_llm_class.return_value = MagicMock()

        from email_agent.services.style_learner import StyleLearner, StyleAnalysis

        learner = StyleLearner()
        analysis = StyleAnalysis(
            tone="casual",
            greeting_used="Hi John,",
            formality_score=0.3,
            response_length="short",
            topics_discussed=[],
        )

        result = learner.merge_style(None, analysis)

        assert result.tone == "casual"
        assert result.greeting_preference == "Hi John,"
        assert result.formality_score == 0.3
        assert result.avg_response_length == "short"
        assert result.sample_count == 1

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_merge_style_with_existing(self, mock_settings, mock_llm_class, mock_store):
        """Test merging with existing style uses weighted average."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_llm_class.return_value = MagicMock()

        from email_agent.services.style_learner import StyleLearner, StyleAnalysis

        learner = StyleLearner()
        existing = ContactStyle(
            tone="formal",
            greeting_preference="Dear John,",
            formality_score=0.8,
            avg_response_length="long",
            sample_count=5,
        )
        analysis = StyleAnalysis(
            tone="casual",
            greeting_used="Hi John,",
            formality_score=0.2,
            response_length="short",
            topics_discussed=[],
        )

        result = learner.merge_style(existing, analysis)

        # Formality should be weighted average (0.7 * 0.8 + 0.3 * 0.2 = 0.62)
        assert result.formality_score == pytest.approx(0.62, rel=0.01)
        # Greeting should be updated to new
        assert result.greeting_preference == "Hi John,"
        # Sample count should increment
        assert result.sample_count == 6

    @patch("email_agent.services.style_learner.contact_memory_store")
    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_merge_style_keeps_existing_greeting_if_none_provided(
        self, mock_settings, mock_llm_class, mock_store
    ):
        """Test that empty greeting doesn't overwrite existing."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_llm_class.return_value = MagicMock()

        from email_agent.services.style_learner import StyleLearner, StyleAnalysis

        learner = StyleLearner()
        existing = ContactStyle(
            greeting_preference="Hi John,",
            formality_score=0.5,
            sample_count=2,
        )
        analysis = StyleAnalysis(
            tone="formal",
            greeting_used="",  # No greeting in this email
            formality_score=0.6,
            response_length="medium",
            topics_discussed=[],
        )

        result = learner.merge_style(existing, analysis)
        assert result.greeting_preference == "Hi John,"


class TestStyleLearnerLearnFromEmail:
    """Tests for StyleLearner.learn_from_sent_email integration."""

    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_learn_from_sent_email_updates_memory(self, mock_settings, mock_llm_class):
        """Test that learning updates contact memory."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "tone": "casual",
            "greeting_used": "Hi John,",
            "formality_score": 0.3,
            "response_length": "short",
            "topics_discussed": ["meeting"],
        })
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        mock_memory_store = MagicMock(spec=ContactMemoryStore)
        mock_memory_store.get_contact.return_value = None

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner(memory_store=mock_memory_store)
        learner.learn_from_sent_email(
            sent_body="Hi John, Let's meet tomorrow.",
            recipient_email="john@example.com",
            recipient_name="John Doe",
        )

        # Verify style was updated
        mock_memory_store.update_style.assert_called_once()
        # Verify name was updated
        mock_memory_store.update_contact_name.assert_called_once_with(
            "john@example.com", "John Doe"
        )
        # Verify topic was added
        mock_memory_store.add_topic.assert_called_once()

    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_learn_from_sent_email_handles_errors(self, mock_settings, mock_llm_class):
        """Test that errors are handled gracefully."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_llm_class.return_value = MagicMock()

        mock_memory_store = MagicMock(spec=ContactMemoryStore)
        mock_memory_store.get_contact.side_effect = Exception("DB error")

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner(memory_store=mock_memory_store)

        # Should not raise, just log warning
        learner.learn_from_sent_email(
            sent_body="Test",
            recipient_email="test@example.com",
        )

    @patch("email_agent.services.style_learner.ChatOpenAI")
    @patch("email_agent.services.style_learner.settings")
    def test_learn_from_sent_email_skips_empty_topics(
        self, mock_settings, mock_llm_class
    ):
        """Test that empty topics are not added."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "tone": "formal",
            "greeting_used": "",
            "formality_score": 0.7,
            "response_length": "medium",
            "topics_discussed": ["", "  ", "valid topic"],
        })
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        mock_memory_store = MagicMock(spec=ContactMemoryStore)
        mock_memory_store.get_contact.return_value = None

        from email_agent.services.style_learner import StyleLearner

        learner = StyleLearner(memory_store=mock_memory_store)
        learner.learn_from_sent_email(
            sent_body="Test email",
            recipient_email="test@example.com",
        )

        # Should only add the valid topic
        assert mock_memory_store.add_topic.call_count == 1
