"""
Contact memory storage for learning user's writing style per sender.

Stores writing style preferences and conversation topics per contact.
Uses Firestore in production and local JSON in development.
Auto-expires after 6 months of inactivity via Firestore TTL.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# TTL duration for contact memory (6 months)
CONTACT_TTL_DAYS = 180


@dataclass
class ContactStyle:
    """Writing style profile for a contact."""

    tone: str = "formal"  # "formal" | "casual" | "mixed"
    greeting_preference: str = ""  # e.g., "Hi John," or "Dear Mr. Smith,"
    formality_score: float = 0.5  # 0.0 (casual) to 1.0 (formal)
    avg_response_length: str = "medium"  # "short" | "medium" | "long"
    sample_count: int = 0  # Number of emails analyzed


@dataclass
class ContactTopic:
    """A conversation topic with a contact."""

    topic: str
    last_mentioned: str  # ISO format datetime
    context_snippet: str = ""  # Brief context from the conversation


@dataclass
class ContactMemory:
    """Full memory record for a contact."""

    email: str
    name: str = ""
    style: ContactStyle = field(default_factory=ContactStyle)
    topics: list[ContactTopic] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    expires_at: str = ""
    email_count: int = 0

    def __post_init__(self):
        """Set timestamps if not provided."""
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.expires_at:
            expires = datetime.utcnow() + timedelta(days=CONTACT_TTL_DAYS)
            self.expires_at = expires.isoformat() + "Z"

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore storage."""
        return {
            "email": self.email,
            "name": self.name,
            "style": asdict(self.style),
            "topics": [asdict(t) for t in self.topics],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "email_count": self.email_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContactMemory":
        """Create from Firestore document data."""
        style_data = data.get("style", {})
        topics_data = data.get("topics", [])

        return cls(
            email=data.get("email", ""),
            name=data.get("name", ""),
            style=ContactStyle(**style_data) if style_data else ContactStyle(),
            topics=[ContactTopic(**t) for t in topics_data],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            expires_at=data.get("expires_at", ""),
            email_count=data.get("email_count", 0),
        )


class ContactMemoryStore:
    """
    Firestore storage for contact memory.

    In production (Cloud Run): Uses Firestore.
    In development: Uses a local JSON file.
    """

    MAX_TOPICS = 10  # Rolling window of topics per contact

    def __init__(
        self,
        collection_name: str = "contact_memory",
        local_file_path: str = ".contact_memory.json",
    ) -> None:
        """
        Initialize the contact memory store.

        Args:
            collection_name: Firestore collection name.
            local_file_path: Path for local JSON file (development).
        """
        self.collection_name = collection_name
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

    def _normalize_email(self, email: str) -> str:
        """Normalize email to lowercase for consistent document IDs."""
        return email.lower().strip()

    def get_contact(self, email: str) -> ContactMemory | None:
        """
        Fetch memory for a specific contact.

        Args:
            email: Contact's email address.

        Returns:
            ContactMemory if found, None otherwise.
        """
        email = self._normalize_email(email)

        if self._is_cloud_run:
            return self._get_from_firestore(email)
        else:
            return self._get_from_local_file(email)

    def upsert_contact(self, memory: ContactMemory) -> None:
        """
        Create or update contact memory.

        Args:
            memory: ContactMemory to store.
        """
        memory.email = self._normalize_email(memory.email)
        memory.updated_at = datetime.utcnow().isoformat() + "Z"
        # Reset expiration on update
        memory.expires_at = (
            datetime.utcnow() + timedelta(days=CONTACT_TTL_DAYS)
        ).isoformat() + "Z"

        if self._is_cloud_run:
            self._save_to_firestore(memory)
        else:
            self._save_to_local_file(memory)

        logger.info(f"Updated contact memory for: {memory.email}")

    def update_style(self, email: str, style: ContactStyle) -> None:
        """
        Update just the style portion of a contact's memory.

        Args:
            email: Contact's email address.
            style: New style to merge/update.
        """
        email = self._normalize_email(email)
        existing = self.get_contact(email)

        if existing:
            existing.style = style
            existing.email_count += 1
            self.upsert_contact(existing)
        else:
            # Create new contact with just style
            memory = ContactMemory(
                email=email,
                style=style,
                email_count=1,
            )
            self.upsert_contact(memory)

    def add_topic(self, email: str, topic: ContactTopic) -> None:
        """
        Add a topic to contact's memory, maintaining rolling window.

        Args:
            email: Contact's email address.
            topic: Topic to add.
        """
        email = self._normalize_email(email)
        existing = self.get_contact(email)

        if existing:
            # Add topic and maintain max size
            existing.topics.insert(0, topic)
            existing.topics = existing.topics[: self.MAX_TOPICS]
            self.upsert_contact(existing)
        else:
            # Create new contact with just this topic
            memory = ContactMemory(
                email=email,
                topics=[topic],
            )
            self.upsert_contact(memory)

    def update_contact_name(self, email: str, name: str) -> None:
        """
        Update the contact's name.

        Args:
            email: Contact's email address.
            name: Contact's name.
        """
        email = self._normalize_email(email)
        existing = self.get_contact(email)

        if existing:
            if not existing.name and name:
                existing.name = name
                self.upsert_contact(existing)
        else:
            memory = ContactMemory(email=email, name=name)
            self.upsert_contact(memory)

    # =========================================================================
    # Firestore Operations
    # =========================================================================

    def _get_from_firestore(self, email: str) -> ContactMemory | None:
        """Load contact memory from Firestore."""
        try:
            client = self._get_firestore_client()
            doc_ref = client.collection(self.collection_name).document(email)
            doc = doc_ref.get()

            if doc.exists:
                return ContactMemory.from_dict(doc.to_dict())

            return None

        except Exception as e:
            logger.error(f"Failed to read contact from Firestore: {e}")
            return None

    def _save_to_firestore(self, memory: ContactMemory) -> None:
        """Save contact memory to Firestore."""
        try:
            client = self._get_firestore_client()
            doc_ref = client.collection(self.collection_name).document(memory.email)
            doc_ref.set(memory.to_dict(), merge=True)

        except Exception as e:
            logger.error(f"Failed to write contact to Firestore: {e}")
            raise

    # =========================================================================
    # Local File Operations (Development)
    # =========================================================================

    def _get_from_local_file(self, email: str) -> ContactMemory | None:
        """Load contact memory from local JSON file."""
        try:
            if not self.local_file_path.exists():
                return None

            data = json.loads(self.local_file_path.read_text())
            contacts = data.get("contacts", {})

            if email in contacts:
                return ContactMemory.from_dict(contacts[email])

            return None

        except Exception as e:
            logger.error(f"Failed to read local contact file: {e}")
            return None

    def _save_to_local_file(self, memory: ContactMemory) -> None:
        """Save contact memory to local JSON file."""
        try:
            # Load existing data
            if self.local_file_path.exists():
                data = json.loads(self.local_file_path.read_text())
            else:
                data = {"contacts": {}}

            # Update contact
            data["contacts"][memory.email] = memory.to_dict()

            # Save
            self.local_file_path.write_text(json.dumps(data, indent=2))

        except Exception as e:
            logger.error(f"Failed to write local contact file: {e}")
            raise


# Singleton instance for easy import
contact_memory_store = ContactMemoryStore()
