"""
Gmail label management for the email agent workflow.

Manages the three workflow labels:
- "Agent Respond": User applies this to trigger the agent
- "Agent Done": Agent applies after successful processing
- "Agent Pending": Agent applies when user decision is required
"""

import logging
from functools import lru_cache

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.config import settings
from email_agent.gmail.auth import get_gmail_service

logger = logging.getLogger(__name__)


class GmailLabelManager:
    """
    Manages Gmail labels for the agent workflow.

    Gmail labels have two parts:
    - name: Human-readable ("Agent Respond")
    - id: Internal ID used by API ("Label_123456789")

    This class handles the mapping and provides easy methods
    to add/remove labels from messages.
    """

    # Label configuration with colors
    # Colors help users identify agent labels at a glance
    LABEL_COLORS = {
        "Agent Respond": {
            "backgroundColor": "#16a765",  # Green - action needed
            "textColor": "#ffffff",
        },
        "Agent Done": {
            "backgroundColor": "#4986e7",  # Blue - completed
            "textColor": "#ffffff",
        },
        "Agent Pending": {
            "backgroundColor": "#ffad47",  # Orange - waiting
            "textColor": "#ffffff",
        },
    }

    def __init__(self, gmail_service: Resource | None = None) -> None:
        """
        Initialize the label manager.

        Args:
            gmail_service: Gmail API service. If None, will be auto-created.
        """
        self._service = gmail_service
        self._label_cache: dict[str, str] = {}  # name -> id mapping

    @property
    def service(self) -> Resource:
        """Get Gmail service, creating if needed."""
        if self._service is None:
            self._service = get_gmail_service()
        return self._service

    def ensure_labels_exist(self) -> dict[str, str]:
        """
        Ensure all agent labels exist in Gmail.

        Creates any missing labels with appropriate colors.

        Returns:
            Dictionary mapping label names to their IDs.
        """
        label_names = [
            settings.label_agent_respond,
            settings.label_agent_done,
            settings.label_agent_pending,
        ]

        result = {}

        for name in label_names:
            label_id = self.get_label_id(name)

            if label_id is None:
                # Label doesn't exist, create it
                label_id = self._create_label(name)
                logger.info(f"Created label '{name}' with ID: {label_id}")
            else:
                logger.debug(f"Label '{name}' already exists with ID: {label_id}")

            result[name] = label_id

        return result

    def get_label_id(self, label_name: str) -> str | None:
        """
        Get the ID for a label by its name.

        Args:
            label_name: The human-readable label name.

        Returns:
            The label ID, or None if not found.
        """
        # Check cache first
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        # Fetch all labels from Gmail
        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels = response.get("labels", [])

            # Build cache and find our label
            for label in labels:
                self._label_cache[label["name"]] = label["id"]

            return self._label_cache.get(label_name)

        except HttpError as e:
            logger.error(f"Failed to list labels: {e}")
            return None

    def _create_label(self, label_name: str) -> str:
        """
        Create a new label in Gmail.

        Args:
            label_name: The name for the new label.

        Returns:
            The ID of the created label.
        """
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",  # Show in label list
            "messageListVisibility": "show",  # Show in message list
        }

        # Add color if configured
        if label_name in self.LABEL_COLORS:
            label_body["color"] = self.LABEL_COLORS[label_name]

        try:
            result = (
                self.service.users()
                .labels()
                .create(userId="me", body=label_body)
                .execute()
            )

            label_id = result["id"]
            self._label_cache[label_name] = label_id

            return label_id

        except HttpError as e:
            logger.error(f"Failed to create label '{label_name}': {e}")
            raise

    def add_label(self, message_id: str, label_name: str) -> None:
        """
        Add a label to a message.

        Args:
            message_id: The Gmail message ID.
            label_name: The label name to add.
        """
        label_id = self.get_label_id(label_name)

        if label_id is None:
            raise ValueError(f"Label '{label_name}' not found. Run ensure_labels_exist() first.")

        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]},
            ).execute()

            logger.debug(f"Added label '{label_name}' to message {message_id}")

        except HttpError as e:
            logger.error(f"Failed to add label '{label_name}' to message {message_id}: {e}")
            raise

    def remove_label(self, message_id: str, label_name: str) -> None:
        """
        Remove a label from a message.

        Args:
            message_id: The Gmail message ID.
            label_name: The label name to remove.
        """
        label_id = self.get_label_id(label_name)

        if label_id is None:
            logger.warning(f"Label '{label_name}' not found, nothing to remove")
            return

        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": [label_id]},
            ).execute()

            logger.debug(f"Removed label '{label_name}' from message {message_id}")

        except HttpError as e:
            logger.error(f"Failed to remove label '{label_name}' from message {message_id}: {e}")
            raise

    def get_message_labels(self, message_id: str) -> list[str]:
        """
        Get all label IDs for a message.

        Args:
            message_id: The Gmail message ID.

        Returns:
            List of label IDs on the message.
        """
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="minimal")
                .execute()
            )

            return message.get("labelIds", [])

        except HttpError as e:
            logger.error(f"Failed to get labels for message {message_id}: {e}")
            return []

    def has_label(self, message_id: str, label_name: str) -> bool:
        """
        Check if a message has a specific label.

        Args:
            message_id: The Gmail message ID.
            label_name: The label name to check for.

        Returns:
            True if the message has the label, False otherwise.
        """
        label_id = self.get_label_id(label_name)

        if label_id is None:
            return False

        message_labels = self.get_message_labels(message_id)
        return label_id in message_labels

    def transition_to_done(self, message_id: str) -> None:
        """
        Transition a message from "Agent Respond" to "Agent Done".

        This is a convenience method for the common workflow transition.

        Args:
            message_id: The Gmail message ID.
        """
        respond_id = self.get_label_id(settings.label_agent_respond)
        done_id = self.get_label_id(settings.label_agent_done)

        if respond_id is None or done_id is None:
            raise ValueError("Agent labels not found. Run ensure_labels_exist() first.")

        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "addLabelIds": [done_id],
                    "removeLabelIds": [respond_id],
                },
            ).execute()

            logger.info(f"Transitioned message {message_id} to 'Agent Done'")

        except HttpError as e:
            logger.error(f"Failed to transition message {message_id}: {e}")
            raise

    def transition_to_pending(self, message_id: str) -> None:
        """
        Transition a message from "Agent Respond" to "Agent Pending".

        Used when the agent needs user input before responding.

        Args:
            message_id: The Gmail message ID.
        """
        respond_id = self.get_label_id(settings.label_agent_respond)
        pending_id = self.get_label_id(settings.label_agent_pending)

        if respond_id is None or pending_id is None:
            raise ValueError("Agent labels not found. Run ensure_labels_exist() first.")

        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "addLabelIds": [pending_id],
                    "removeLabelIds": [respond_id],
                },
            ).execute()

            logger.info(f"Transitioned message {message_id} to 'Agent Pending'")

        except HttpError as e:
            logger.error(f"Failed to transition message {message_id}: {e}")
            raise


# Singleton instance for easy import
label_manager = GmailLabelManager()
