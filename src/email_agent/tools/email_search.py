"""Email search tool for finding past emails."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import logging

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.gmail.auth import get_gmail_service
from email_agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class EmailSummary:
    """Summary of an email from search results."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    date: datetime
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "date": self.date.isoformat(),
            "snippet": self.snippet,
        }

    def __str__(self) -> str:
        """Format for display."""
        date_str = self.date.strftime("%b %d, %Y")
        return f"[{date_str}] {self.sender}: {self.subject}"


@dataclass
class SearchResults:
    """Results from email search."""

    query: str
    total_count: int
    emails: list[EmailSummary]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "total_count": self.total_count,
            "emails": [email.to_dict() for email in self.emails],
            "summary": self.get_summary(),
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if not self.emails:
            return f"No emails found matching: {self.query}"

        lines = [f"Found {self.total_count} email(s) matching '{self.query}':"]
        for email in self.emails[:5]:
            lines.append(f"  - {email}")

        if len(self.emails) > 5:
            lines.append(f"  ... and {self.total_count - 5} more")

        return "\n".join(lines)


class EmailSearchTool(BaseTool):
    """Tool to search past emails."""

    def __init__(self, gmail_service: Resource | None = None):
        """Initialize with optional Gmail service for testing."""
        self._service = gmail_service

    @property
    def service(self) -> Resource:
        """Get Gmail service, initializing if needed."""
        if self._service is None:
            self._service = get_gmail_service()
        return self._service

    @property
    def name(self) -> str:
        return "search_emails"

    @property
    def description(self) -> str:
        return (
            "Search through past emails using Gmail query syntax. "
            "Use this when someone references a previous email, proposal, "
            "document, or conversation. Examples: 'from:john proposal', "
            "'subject:invoice after:2024/01/01', 'has:attachment contract'"
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Gmail search query. Supports: from:, to:, subject:, "
                        "has:attachment, after:, before:, is:unread, label:, "
                        "and free text search."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return. Default: 5",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def execute(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Search emails using Gmail query syntax.

        Args:
            query: Gmail search query string
            max_results: Maximum number of results (default: 5)

        Returns:
            ToolResult with SearchResults data
        """
        if not query or not query.strip():
            return ToolResult.fail("Search query cannot be empty")

        try:
            logger.info(f"Searching emails with query: {query}")

            # Search for messages
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            total_count = results.get("resultSizeEstimate", len(messages))

            if not messages:
                return ToolResult.empty(f"No emails found matching: {query}")

            # Fetch details for each message
            email_summaries = []
            for msg in messages:
                summary = self._get_email_summary(msg["id"])
                if summary:
                    email_summaries.append(summary)

            search_results = SearchResults(
                query=query,
                total_count=total_count,
                emails=email_summaries,
            )

            return ToolResult.ok(
                search_results.to_dict(),
                result_count=len(email_summaries),
            )

        except HttpError as e:
            logger.error(f"Gmail API error during search: {e}")
            return ToolResult.fail(f"Gmail API error: {e.reason}")

    def _get_email_summary(self, message_id: str) -> EmailSummary | None:
        """Fetch email details and create summary."""
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="metadata")
                .execute()
            )

            headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}

            # Parse date
            date_str = headers.get("date", "")
            date = self._parse_email_date(date_str)

            # Extract sender name/email
            sender = headers.get("from", "Unknown")

            return EmailSummary(
                message_id=message_id,
                thread_id=message.get("threadId", ""),
                subject=headers.get("subject", "(no subject)"),
                sender=sender,
                date=date,
                snippet=message.get("snippet", ""),
            )

        except HttpError as e:
            logger.warning(f"Failed to fetch message {message_id}: {e}")
            return None

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date header to datetime."""
        if not date_str:
            return datetime.now()

        # Common email date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]

        # Remove timezone abbreviations in parentheses like (PST)
        import re
        date_str = re.sub(r"\s*\([A-Z]{2,4}\)\s*$", "", date_str)

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        # Fallback to now if parsing fails
        logger.warning(f"Could not parse email date: {date_str}")
        return datetime.now()

    def build_query(
        self,
        from_email: str | None = None,
        to_email: str | None = None,
        subject: str | None = None,
        keywords: str | None = None,
        after: str | None = None,
        before: str | None = None,
        has_attachment: bool = False,
        is_unread: bool | None = None,
    ) -> str:
        """
        Build a Gmail search query from parameters.

        Helper method for constructing complex queries.

        Args:
            from_email: Filter by sender
            to_email: Filter by recipient
            subject: Filter by subject line
            keywords: Free text search
            after: Date in YYYY/MM/DD format
            before: Date in YYYY/MM/DD format
            has_attachment: Filter for emails with attachments
            is_unread: Filter by read/unread status

        Returns:
            Gmail query string
        """
        parts = []

        if from_email:
            parts.append(f"from:{from_email}")
        if to_email:
            parts.append(f"to:{to_email}")
        if subject:
            parts.append(f"subject:{subject}")
        if keywords:
            parts.append(keywords)
        if after:
            parts.append(f"after:{after}")
        if before:
            parts.append(f"before:{before}")
        if has_attachment:
            parts.append("has:attachment")
        if is_unread is True:
            parts.append("is:unread")
        elif is_unread is False:
            parts.append("is:read")

        return " ".join(parts)


# Singleton instance
email_search_tool = EmailSearchTool()
