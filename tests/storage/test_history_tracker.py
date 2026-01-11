"""Tests for the history tracker module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from email_agent.storage.history_tracker import HistoryTracker


class TestHistoryTrackerLocal:
    """Tests for local file-based history tracking (development mode)."""

    def test_get_history_id_no_file(self, tmp_path):
        """Test getting history ID when no file exists."""
        tracker = HistoryTracker(local_file_path=str(tmp_path / "history.json"))

        result = tracker.get_last_history_id()

        assert result is None

    def test_save_and_get_history_id(self, tmp_path):
        """Test saving and retrieving history ID."""
        file_path = tmp_path / "history.json"
        tracker = HistoryTracker(local_file_path=str(file_path))

        # Save
        tracker.update_history_id(12345)

        # Verify file was created
        assert file_path.exists()

        # Retrieve
        result = tracker.get_last_history_id()
        assert result == 12345

    def test_update_history_id_overwrites(self, tmp_path):
        """Test that updating history ID overwrites the previous value."""
        tracker = HistoryTracker(local_file_path=str(tmp_path / "history.json"))

        tracker.update_history_id(100)
        tracker.update_history_id(200)
        tracker.update_history_id(300)

        result = tracker.get_last_history_id()
        assert result == 300

    def test_file_format(self, tmp_path):
        """Test that the saved file has correct JSON format."""
        file_path = tmp_path / "history.json"
        tracker = HistoryTracker(local_file_path=str(file_path))

        tracker.update_history_id(99999)

        data = json.loads(file_path.read_text())
        assert data == {"last_history_id": 99999}

    def test_corrupted_file_returns_none(self, tmp_path):
        """Test that corrupted file returns None gracefully."""
        file_path = tmp_path / "history.json"
        file_path.write_text("not valid json {{{")

        tracker = HistoryTracker(local_file_path=str(file_path))

        result = tracker.get_last_history_id()
        assert result is None


class TestHistoryTrackerFirestore:
    """Tests for Firestore-based history tracking (production mode)."""

    @patch.dict("os.environ", {"K_SERVICE": "email-agent"})
    @patch("email_agent.storage.history_tracker.HistoryTracker._get_firestore_client")
    def test_get_history_id_from_firestore(self, mock_get_client):
        """Test getting history ID from Firestore."""
        # Setup mock
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"last_history_id": 54321}

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection
        mock_get_client.return_value = mock_client

        tracker = HistoryTracker()

        result = tracker.get_last_history_id()

        assert result == 54321
        mock_client.collection.assert_called_with("email_agent_state")
        mock_collection.document.assert_called_with("gmail_history")

    @patch.dict("os.environ", {"K_SERVICE": "email-agent"})
    @patch("email_agent.storage.history_tracker.HistoryTracker._get_firestore_client")
    def test_get_history_id_no_document(self, mock_get_client):
        """Test getting history ID when Firestore document doesn't exist."""
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection
        mock_get_client.return_value = mock_client

        tracker = HistoryTracker()

        result = tracker.get_last_history_id()

        assert result is None

    @patch.dict("os.environ", {"K_SERVICE": "email-agent"})
    @patch("email_agent.storage.history_tracker.HistoryTracker._get_firestore_client")
    def test_save_history_id_to_firestore(self, mock_get_client):
        """Test saving history ID to Firestore."""
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection
        mock_get_client.return_value = mock_client

        tracker = HistoryTracker()

        tracker.update_history_id(11111)

        mock_doc_ref.set.assert_called_once_with(
            {"last_history_id": 11111}, merge=True
        )
