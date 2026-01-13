"""Unit tests for contact memory storage."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from email_agent.storage.contact_memory import (
    ContactMemoryStore,
    ContactMemory,
    ContactStyle,
    ContactTopic,
    CONTACT_TTL_DAYS,
)


class TestContactStyle:
    """Tests for ContactStyle dataclass."""

    def test_default_values(self):
        """Test default values for ContactStyle."""
        style = ContactStyle()
        assert style.tone == "formal"
        assert style.greeting_preference == ""
        assert style.formality_score == 0.5
        assert style.avg_response_length == "medium"
        assert style.sample_count == 0

    def test_custom_values(self):
        """Test custom values for ContactStyle."""
        style = ContactStyle(
            tone="casual",
            greeting_preference="Hi John,",
            formality_score=0.3,
            avg_response_length="short",
            sample_count=5,
        )
        assert style.tone == "casual"
        assert style.greeting_preference == "Hi John,"
        assert style.formality_score == 0.3
        assert style.avg_response_length == "short"
        assert style.sample_count == 5


class TestContactTopic:
    """Tests for ContactTopic dataclass."""

    def test_topic_creation(self):
        """Test creating a ContactTopic."""
        topic = ContactTopic(
            topic="Project Alpha",
            last_mentioned="2025-01-10T14:30:00Z",
            context_snippet="Discussed timeline",
        )
        assert topic.topic == "Project Alpha"
        assert topic.last_mentioned == "2025-01-10T14:30:00Z"
        assert topic.context_snippet == "Discussed timeline"


class TestContactMemory:
    """Tests for ContactMemory dataclass."""

    def test_default_timestamps(self):
        """Test that timestamps are auto-set."""
        memory = ContactMemory(email="test@example.com")
        assert memory.created_at != ""
        assert memory.updated_at != ""
        assert memory.expires_at != ""

    def test_expires_at_in_future(self):
        """Test that expires_at is set to future."""
        memory = ContactMemory(email="test@example.com")
        # Parse expires_at and check it's in the future
        expires = datetime.fromisoformat(memory.expires_at.rstrip("Z"))
        now = datetime.utcnow()
        assert expires > now
        # Should be approximately CONTACT_TTL_DAYS in future
        delta = expires - now
        assert delta.days >= CONTACT_TTL_DAYS - 1

    def test_to_dict(self):
        """Test converting to dictionary."""
        memory = ContactMemory(
            email="test@example.com",
            name="Test User",
            style=ContactStyle(tone="casual"),
            topics=[ContactTopic(topic="Test", last_mentioned="2025-01-10T00:00:00Z")],
        )
        data = memory.to_dict()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["style"]["tone"] == "casual"
        assert len(data["topics"]) == 1

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "email": "test@example.com",
            "name": "Test User",
            "style": {"tone": "casual", "formality_score": 0.3},
            "topics": [{"topic": "Test", "last_mentioned": "2025-01-10T00:00:00Z"}],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-10T00:00:00Z",
            "expires_at": "2025-07-01T00:00:00Z",
            "email_count": 5,
        }
        memory = ContactMemory.from_dict(data)
        assert memory.email == "test@example.com"
        assert memory.name == "Test User"
        assert memory.style.tone == "casual"
        assert memory.style.formality_score == 0.3
        assert len(memory.topics) == 1
        assert memory.email_count == 5


class TestContactMemoryStoreLocal:
    """Tests for ContactMemoryStore using local file storage."""

    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create a store with temporary file path."""
        store = ContactMemoryStore(
            collection_name="test_contacts",
            local_file_path=str(tmp_path / ".test_contacts.json"),
        )
        # Force local mode
        store._is_cloud_run = False
        return store

    def test_get_contact_not_found(self, temp_store):
        """Test getting non-existent contact returns None."""
        result = temp_store.get_contact("nonexistent@example.com")
        assert result is None

    def test_upsert_and_get_contact(self, temp_store):
        """Test creating and retrieving a contact."""
        memory = ContactMemory(
            email="Test@Example.com",  # Test normalization
            name="Test User",
            style=ContactStyle(tone="casual"),
        )
        temp_store.upsert_contact(memory)

        # Retrieve (should normalize email)
        result = temp_store.get_contact("TEST@EXAMPLE.COM")
        assert result is not None
        assert result.email == "test@example.com"
        assert result.name == "Test User"
        assert result.style.tone == "casual"

    def test_update_style(self, temp_store):
        """Test updating just the style."""
        # Create initial contact with email_count=1
        memory = ContactMemory(email="test@example.com", email_count=1)
        temp_store.upsert_contact(memory)

        # Update style
        new_style = ContactStyle(tone="casual", formality_score=0.2, sample_count=1)
        temp_store.update_style("test@example.com", new_style)

        # Verify
        result = temp_store.get_contact("test@example.com")
        assert result.style.tone == "casual"
        assert result.style.formality_score == 0.2
        assert result.email_count == 2  # Incremented from 1

    def test_update_style_creates_contact(self, temp_store):
        """Test that update_style creates contact if not exists."""
        new_style = ContactStyle(tone="casual")
        temp_store.update_style("new@example.com", new_style)

        result = temp_store.get_contact("new@example.com")
        assert result is not None
        assert result.style.tone == "casual"
        assert result.email_count == 1

    def test_add_topic(self, temp_store):
        """Test adding a topic."""
        memory = ContactMemory(email="test@example.com")
        temp_store.upsert_contact(memory)

        topic = ContactTopic(
            topic="Project Alpha",
            last_mentioned="2025-01-10T00:00:00Z",
        )
        temp_store.add_topic("test@example.com", topic)

        result = temp_store.get_contact("test@example.com")
        assert len(result.topics) == 1
        assert result.topics[0].topic == "Project Alpha"

    def test_add_topic_rolling_window(self, temp_store):
        """Test that topics are limited to MAX_TOPICS."""
        memory = ContactMemory(email="test@example.com")
        temp_store.upsert_contact(memory)

        # Add more than MAX_TOPICS
        for i in range(15):
            topic = ContactTopic(
                topic=f"Topic {i}",
                last_mentioned=f"2025-01-{i+1:02d}T00:00:00Z",
            )
            temp_store.add_topic("test@example.com", topic)

        result = temp_store.get_contact("test@example.com")
        assert len(result.topics) == temp_store.MAX_TOPICS
        # Most recent should be first
        assert result.topics[0].topic == "Topic 14"

    def test_update_contact_name(self, temp_store):
        """Test updating contact name."""
        memory = ContactMemory(email="test@example.com")
        temp_store.upsert_contact(memory)

        temp_store.update_contact_name("test@example.com", "John Doe")

        result = temp_store.get_contact("test@example.com")
        assert result.name == "John Doe"

    def test_update_contact_name_does_not_overwrite(self, temp_store):
        """Test that existing name is not overwritten."""
        memory = ContactMemory(email="test@example.com", name="Original Name")
        temp_store.upsert_contact(memory)

        temp_store.update_contact_name("test@example.com", "New Name")

        result = temp_store.get_contact("test@example.com")
        assert result.name == "Original Name"

    def test_normalize_email(self, temp_store):
        """Test email normalization."""
        assert temp_store._normalize_email("Test@Example.COM") == "test@example.com"
        assert temp_store._normalize_email("  user@test.com  ") == "user@test.com"


class TestContactMemoryStoreFirestore:
    """Tests for ContactMemoryStore using Firestore (mocked)."""

    @pytest.fixture
    def mock_firestore_store(self):
        """Create a store with mocked Firestore."""
        store = ContactMemoryStore(collection_name="test_contacts")
        store._is_cloud_run = True
        return store

    def test_get_contact_from_firestore(self, mock_firestore_store):
        """Test getting contact from Firestore."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "style": {"tone": "casual"},
            "topics": [],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-10T00:00:00Z",
            "expires_at": "2025-07-01T00:00:00Z",
            "email_count": 5,
        }

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        mock_firestore_store._firestore_client = mock_client

        result = mock_firestore_store.get_contact("test@example.com")
        assert result is not None
        assert result.email == "test@example.com"
        assert result.style.tone == "casual"

    def test_save_to_firestore(self, mock_firestore_store):
        """Test saving contact to Firestore."""
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        mock_firestore_store._firestore_client = mock_client

        memory = ContactMemory(email="test@example.com", name="Test User")
        mock_firestore_store.upsert_contact(memory)

        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args
        assert call_args[0][0]["email"] == "test@example.com"
        assert call_args[1]["merge"] is True
