"""
Gmail watch management for push notifications.

Sets up and maintains Gmail push notifications via Pub/Sub.
Gmail watches expire after 7 days and must be renewed.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.config import settings
from email_agent.gmail.auth import get_gmail_service
from email_agent.gmail.labels import label_manager

logger = logging.getLogger(__name__)


@dataclass
class WatchResponse:
    """Response from setting up a Gmail watch."""

    history_id: int
    expiration: datetime


class GmailWatchService:
    """
    Manages Gmail push notification watches.

    Gmail watches:
    - Tell Gmail to send notifications to a Pub/Sub topic
    - Expire after 7 days (must be renewed)
    - Can filter by label (we only watch "Agent Respond")

    Typical flow:
    1. Call setup_watch() on app startup or deployment
    2. Cloud Scheduler calls renew_watch() every 6 days
    3. Gmail sends notifications to Pub/Sub when labels change
    """

    def __init__(self, gmail_service: Resource | None = None) -> None:
        """
        Initialize the watch service.

        Args:
            gmail_service: Gmail API service. If None, will be auto-created.
        """
        self._service = gmail_service

    @property
    def service(self) -> Resource:
        """Get Gmail service, creating if needed."""
        if self._service is None:
            self._service = get_gmail_service()
        return self._service

    def setup_watch(
        self,
        topic_name: str | None = None,
        label_name: str | None = None,
    ) -> WatchResponse:
        """
        Set up Gmail to push notifications to Pub/Sub.

        Args:
            topic_name: Full Pub/Sub topic name.
                       Format: "projects/{project}/topics/{topic}"
                       If None, uses settings.
            label_name: Label to watch. If None, uses "Agent Respond".

        Returns:
            WatchResponse with history_id and expiration.

        Raises:
            ValueError: If project ID is not configured.
            HttpError: If Gmail API call fails.
        """
        # Build topic name
        if topic_name is None:
            project_id = settings.project_id
            if not project_id:
                raise ValueError(
                    "GCP project ID not configured. "
                    "Set GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable."
                )
            topic_name = f"projects/{project_id}/topics/{settings.pubsub_topic}"

        # Get label ID
        if label_name is None:
            label_name = settings.label_agent_respond

        label_id = label_manager.get_label_id(label_name)

        if label_id is None:
            raise ValueError(
                f"Label '{label_name}' not found. "
                "Run setup_gmail_labels.py first."
            )

        # Set up the watch
        watch_request = {
            "topicName": topic_name,
            "labelIds": [label_id],
            "labelFilterBehavior": "INCLUDE",  # Only notify for this label
        }

        try:
            response = (
                self.service.users()
                .watch(userId="me", body=watch_request)
                .execute()
            )

            # Parse response
            history_id = int(response["historyId"])
            expiration_ms = int(response["expiration"])
            expiration = datetime.fromtimestamp(
                expiration_ms / 1000, tz=timezone.utc
            )

            logger.info(
                f"Gmail watch set up successfully. "
                f"History ID: {history_id}, Expires: {expiration}"
            )

            return WatchResponse(
                history_id=history_id,
                expiration=expiration,
            )

        except HttpError as e:
            logger.error(f"Failed to set up Gmail watch: {e}")
            raise

    def stop_watch(self) -> None:
        """
        Stop the current Gmail watch.

        Call this before setting up a new watch (renewal).
        Safe to call even if no watch is active.
        """
        try:
            self.service.users().stop(userId="me").execute()
            logger.info("Gmail watch stopped")

        except HttpError as e:
            # 404 means no active watch, which is fine
            if e.resp.status == 404:
                logger.debug("No active watch to stop")
            else:
                logger.error(f"Failed to stop Gmail watch: {e}")
                raise

    def renew_watch(
        self,
        topic_name: str | None = None,
        label_name: str | None = None,
    ) -> WatchResponse:
        """
        Renew the Gmail watch.

        Stops any existing watch and creates a new one.
        Should be called every 6 days (watch expires after 7).

        Args:
            topic_name: Full Pub/Sub topic name. If None, uses settings.
            label_name: Label to watch. If None, uses "Agent Respond".

        Returns:
            WatchResponse with new history_id and expiration.
        """
        logger.info("Renewing Gmail watch...")

        # Stop existing watch first
        self.stop_watch()

        # Set up new watch
        return self.setup_watch(topic_name=topic_name, label_name=label_name)

    def get_watch_expiration(self) -> datetime | None:
        """
        Get the current watch expiration time.

        Note: Gmail API doesn't provide a direct way to check watch status.
        This method attempts to set up a watch and returns the expiration.
        If a watch already exists, it will be refreshed.

        Returns:
            Expiration datetime, or None if watch setup fails.
        """
        try:
            # Setting up a watch when one exists just refreshes it
            response = self.setup_watch()
            return response.expiration

        except Exception as e:
            logger.error(f"Failed to get watch expiration: {e}")
            return None


# Singleton instance for easy import
watch_service = GmailWatchService()
