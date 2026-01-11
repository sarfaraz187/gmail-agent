"""
History ID tracker for Gmail push notifications.

Tracks the last processed Gmail historyId to ensure no emails are missed
between push notifications. Uses Firestore in production and local JSON
file in development.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class HistoryTracker:
    """
    Tracks the last processed Gmail history ID.

    In production (Cloud Run): Uses Firestore for persistent storage.
    In development: Uses a local JSON file.

    Why we need this:
    - Gmail push notifications only provide a historyId, not email details
    - We must call history.list(startHistoryId=X) to get changes since X
    - Without tracking, we might miss emails if the app restarts
    """

    def __init__(
        self,
        collection_name: str = "email_agent_state",
        document_id: str = "gmail_history",
        local_file_path: str = ".history_state.json",
    ) -> None:
        """
        Initialize the history tracker.

        Args:
            collection_name: Firestore collection name
            document_id: Firestore document ID
            local_file_path: Path for local JSON file (development)
        """
        self.collection_name = collection_name
        self.document_id = document_id
        self.local_file_path = Path(local_file_path)

        # Detect if running in Cloud Run
        self._is_cloud_run = os.getenv("K_SERVICE") is not None
        self._firestore_client = None

    def _get_firestore_client(self):
        """Lazily initialize Firestore client."""
        if self._firestore_client is None:
            from google.cloud import firestore

            self._firestore_client = firestore.Client()
        return self._firestore_client

    def get_last_history_id(self) -> int | None:
        """
        Get the last processed history ID.

        Returns:
            The last history ID, or None if never set.
        """
        if self._is_cloud_run:
            return self._get_from_firestore()
        else:
            return self._get_from_local_file()

    def update_history_id(self, history_id: int) -> None:
        """
        Update the stored history ID.

        Args:
            history_id: The new history ID to store.
        """
        if self._is_cloud_run:
            self._save_to_firestore(history_id)
        else:
            self._save_to_local_file(history_id)

        logger.info(f"Updated history ID to {history_id}")

    def _get_from_firestore(self) -> int | None:
        """Load history ID from Firestore."""
        try:
            client = self._get_firestore_client()
            doc_ref = client.collection(self.collection_name).document(self.document_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                return data.get("last_history_id")

            logger.info("No history ID found in Firestore (first run)")
            return None

        except Exception as e:
            logger.error(f"Failed to read from Firestore: {e}")
            return None

    def _save_to_firestore(self, history_id: int) -> None:
        """Save history ID to Firestore."""
        try:
            client = self._get_firestore_client()
            doc_ref = client.collection(self.collection_name).document(self.document_id)
            doc_ref.set({"last_history_id": history_id}, merge=True)

        except Exception as e:
            logger.error(f"Failed to write to Firestore: {e}")
            raise

    def _get_from_local_file(self) -> int | None:
        """Load history ID from local JSON file (development)."""
        try:
            if not self.local_file_path.exists():
                logger.info(f"No local history file found at {self.local_file_path}")
                return None

            data = json.loads(self.local_file_path.read_text())
            return data.get("last_history_id")

        except Exception as e:
            logger.error(f"Failed to read local history file: {e}")
            return None

    def _save_to_local_file(self, history_id: int) -> None:
        """Save history ID to local JSON file (development)."""
        try:
            data = {"last_history_id": history_id}
            self.local_file_path.write_text(json.dumps(data, indent=2))

        except Exception as e:
            logger.error(f"Failed to write local history file: {e}")
            raise


# Singleton instance for easy import
history_tracker = HistoryTracker()
