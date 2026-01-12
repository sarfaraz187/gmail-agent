"""
Gmail API client for email operations.

Handles fetching emails, threads, history, and sending replies.
This is the core module for interacting with Gmail.
"""

import base64
import logging
import re
from email.mime.text import MIMEText
from dataclasses import dataclass

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.gmail.auth import get_gmail_service

logger = logging.getLogger(__name__)


# Patterns for senders we should NEVER respond to
NEVER_RESPOND_PATTERNS = [
    r"noreply@",
    r"no-reply@",
    r"donotreply@",
    r"do-not-reply@",
    r"mailer-daemon@",
    r"postmaster@",
    r"notifications@",
    r"notification@",
    r"alert@",
    r"alerts@",
    r"bounce@",
    r"automated@",
    r"auto-reply@",
    r"autoreply@",
]

# Patterns in subject/body indicating auto-reply (out of office, etc.)
AUTO_REPLY_PATTERNS = [
    r"out of office",
    r"out-of-office",
    r"automatic reply",
    r"auto-reply",
    r"autoreply",
    r"away from.*office",
    r"on vacation",
    r"on leave",
    r"currently unavailable",
]


@dataclass
class EmailData:
    """Parsed email data structure."""

    message_id: str  # Gmail's internal API ID
    thread_id: str
    subject: str
    from_email: str
    from_name: str
    to_email: str
    date: str
    body: str
    snippet: str
    labels: list[str]
    rfc_message_id: str | None = None  # RFC 2822 Message-ID header (for threading)
    in_reply_to: str | None = None
    references: str | None = None


@dataclass
class HistoryRecord:
    """A single history change record."""

    history_id: int
    messages_added: list[dict]
    messages_deleted: list[dict]
    labels_added: list[dict]
    labels_removed: list[dict]


class GmailClient:
    """
    Gmail API client for email operations.

    Provides methods to:
    - Fetch email history (changes since last check)
    - Fetch full threads (entire conversations)
    - Send replies (properly threaded)
    - Detect automated/noreply senders
    """

    def __init__(self, gmail_service: Resource | None = None) -> None:
        """
        Initialize the Gmail client.

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

    def get_history(
        self,
        start_history_id: int,
        label_id: str | None = None,
    ) -> list[HistoryRecord]:
        """
        Get all changes since a specific history ID.

        Args:
            start_history_id: Fetch changes after this history ID.
            label_id: Optional label ID to filter by.

        Returns:
            List of history records with changes.
        """
        records = []

        try:
            # Build request parameters
            params = {
                "userId": "me",
                "startHistoryId": start_history_id,
            }

            if label_id:
                params["labelId"] = label_id

            # Fetch history (may be paginated)
            request = self.service.users().history().list(**params)

            while request is not None:
                response = request.execute()
                history_list = response.get("history", [])

                for history in history_list:
                    record = HistoryRecord(
                        history_id=history.get("id", 0),
                        messages_added=[
                            msg.get("message", {})
                            for msg in history.get("messagesAdded", [])
                        ],
                        messages_deleted=[
                            msg.get("message", {})
                            for msg in history.get("messagesDeleted", [])
                        ],
                        labels_added=[
                            msg for msg in history.get("labelsAdded", [])
                        ],
                        labels_removed=[
                            msg for msg in history.get("labelsRemoved", [])
                        ],
                    )
                    records.append(record)

                # Get next page if exists
                request = self.service.users().history().list_next(
                    previous_request=request,
                    previous_response=response,
                )

            logger.debug(f"Fetched {len(records)} history records since {start_history_id}")
            return records

        except HttpError as e:
            if e.resp.status == 404:
                # History ID is too old, need to do a full sync
                logger.warning(f"History ID {start_history_id} is too old, no history available")
                return []
            logger.error(f"Failed to fetch history: {e}")
            raise

    def get_thread(self, thread_id: str) -> list[EmailData]:
        """
        Fetch a complete email thread (conversation).

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            List of EmailData objects, oldest first.
        """
        try:
            thread = (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )

            messages = thread.get("messages", [])
            emails = []

            for message in messages:
                email_data = self._parse_message(message)
                emails.append(email_data)

            logger.debug(f"Fetched thread {thread_id} with {len(emails)} messages")
            return emails

        except HttpError as e:
            logger.error(f"Failed to fetch thread {thread_id}: {e}")
            raise

    def get_message(self, message_id: str) -> EmailData:
        """
        Fetch a single email message.

        Args:
            message_id: The Gmail message ID.

        Returns:
            Parsed EmailData object.
        """
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            return self._parse_message(message)

        except HttpError as e:
            logger.error(f"Failed to fetch message {message_id}: {e}")
            raise

    def send_reply(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> str:
        """
        Send a reply in an existing thread.

        Args:
            thread_id: The thread to reply in.
            to: Recipient email address.
            subject: Email subject (will be prefixed with "Re:" if needed).
            body: Email body text.
            in_reply_to: Message-ID header of the email being replied to.
            references: References header for threading.

        Returns:
            The message ID of the sent reply.
        """
        # Ensure subject has "Re:" prefix
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Create the email message
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        # Add threading headers
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        elif in_reply_to:
            message["References"] = in_reply_to

        # Encode the message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        try:
            result = (
                self.service.users()
                .messages()
                .send(
                    userId="me",
                    body={
                        "raw": raw,
                        "threadId": thread_id,
                    },
                )
                .execute()
            )

            sent_id = result["id"]
            logger.info(f"Sent reply in thread {thread_id}, message ID: {sent_id}")
            return sent_id

        except HttpError as e:
            logger.error(f"Failed to send reply: {e}")
            raise

    def should_skip_sender(self, sender_email: str) -> bool:
        """
        Check if we should skip responding to this sender.

        Detects automated senders like noreply@, mailer-daemon@, etc.

        Args:
            sender_email: The sender's email address.

        Returns:
            True if we should NOT respond to this sender.
        """
        sender_lower = sender_email.lower()

        for pattern in NEVER_RESPOND_PATTERNS:
            if re.search(pattern, sender_lower):
                logger.debug(f"Skipping sender {sender_email} (matches: {pattern})")
                return True

        return False

    def is_auto_reply(self, subject: str, body: str) -> bool:
        """
        Check if an email appears to be an auto-reply.

        Args:
            subject: Email subject.
            body: Email body text.

        Returns:
            True if this looks like an automatic reply.
        """
        text_to_check = f"{subject} {body}".lower()

        for pattern in AUTO_REPLY_PATTERNS:
            if re.search(pattern, text_to_check):
                logger.debug(f"Detected auto-reply (matches: {pattern})")
                return True

        return False

    def _parse_message(self, message: dict) -> EmailData:
        """
        Parse a Gmail API message into EmailData.

        Args:
            message: Raw message from Gmail API.

        Returns:
            Parsed EmailData object.
        """
        headers = {
            h["name"].lower(): h["value"]
            for h in message.get("payload", {}).get("headers", [])
        }

        # Extract sender info
        from_header = headers.get("from", "")
        from_name, from_email = self._parse_email_address(from_header)

        # Extract body
        body = self._extract_body(message.get("payload", {}))

        return EmailData(
            message_id=message["id"],
            thread_id=message["threadId"],
            subject=headers.get("subject", "(no subject)"),
            from_email=from_email,
            from_name=from_name,
            to_email=headers.get("to", ""),
            date=headers.get("date", ""),
            body=body,
            snippet=message.get("snippet", ""),
            labels=message.get("labelIds", []),
            rfc_message_id=headers.get("message-id"),  # RFC 2822 Message-ID for threading
            in_reply_to=headers.get("in-reply-to"),
            references=headers.get("references"),
        )

    def _parse_email_address(self, address: str) -> tuple[str, str]:
        """
        Parse an email address header into name and email.

        Examples:
            "John Smith <john@example.com>" -> ("John Smith", "john@example.com")
            "john@example.com" -> ("", "john@example.com")

        Args:
            address: The email address header.

        Returns:
            Tuple of (name, email).
        """
        # Try to match "Name <email>" format
        match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', address.strip())

        if match:
            name = match.group(1).strip()
            email = match.group(2).strip()
            return name, email

        # Just an email address
        return "", address.strip()

    def _extract_body(self, payload: dict) -> str:
        """
        Extract the plain text body from an email payload.

        Gmail messages can have complex nested MIME structures.
        This method finds the plain text part.

        Args:
            payload: The message payload from Gmail API.

        Returns:
            The plain text body, or empty string if not found.
        """
        # Check for direct body
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        # Check parts (multipart messages)
        parts = payload.get("parts", [])

        for part in parts:
            mime_type = part.get("mimeType", "")

            # Prefer plain text
            if mime_type == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

            # Recurse into nested parts
            if part.get("parts"):
                body = self._extract_body(part)
                if body:
                    return body

        # Fallback: try HTML and strip tags (basic)
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    # Very basic HTML stripping
                    text = re.sub(r"<[^>]+>", "", html)
                    return text

        return ""


# Singleton instance for easy import
gmail_client = GmailClient()
