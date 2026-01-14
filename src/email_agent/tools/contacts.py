"""Contacts lookup tool using Google People API."""

from dataclasses import dataclass, field
from typing import Any
import logging

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.gmail.auth import get_people_service
from email_agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ContactInfo:
    """Contact information from People API."""

    email: str
    name: str | None = None
    phone: str | None = None
    organization: str | None = None
    job_title: str | None = None
    photo_url: str | None = None
    notes: str | None = None
    resource_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "organization": self.organization,
            "job_title": self.job_title,
            "photo_url": self.photo_url,
            "notes": self.notes,
        }

    def __str__(self) -> str:
        """Format for display."""
        parts = []
        if self.name:
            parts.append(self.name)
        if self.job_title and self.organization:
            parts.append(f"{self.job_title} at {self.organization}")
        elif self.organization:
            parts.append(self.organization)
        elif self.job_title:
            parts.append(self.job_title)
        parts.append(f"<{self.email}>")
        return " - ".join(parts)

    def get_display_name(self) -> str:
        """Get best available display name."""
        return self.name or self.email.split("@")[0]


@dataclass
class ContactSearchResults:
    """Results from contact search."""

    query: str
    contacts: list[ContactInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "contacts": [c.to_dict() for c in self.contacts],
            "summary": self.get_summary(),
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        if not self.contacts:
            return f"No contacts found matching: {self.query}"

        lines = [f"Found {len(self.contacts)} contact(s):"]
        for contact in self.contacts[:5]:
            lines.append(f"  - {contact}")

        if len(self.contacts) > 5:
            lines.append(f"  ... and {len(self.contacts) - 5} more")

        return "\n".join(lines)


class ContactLookupTool(BaseTool):
    """Tool to look up contacts using Google People API."""

    def __init__(self, people_service: Resource | None = None):
        """Initialize with optional People service for testing."""
        self._service = people_service

    @property
    def service(self) -> Resource:
        """Get People service, initializing if needed."""
        if self._service is None:
            self._service = get_people_service()
        return self._service

    @property
    def name(self) -> str:
        return "lookup_contact"

    @property
    def description(self) -> str:
        return (
            "Look up contact information by email or name. "
            "Returns name, email, phone, organization, and job title. "
            "Use this to personalize responses or find contact details."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Email address or name to search for",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 5",
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
        Look up contacts by email or name.

        Args:
            query: Email address or name to search
            max_results: Maximum results to return (default: 5)

        Returns:
            ToolResult with ContactSearchResults data
        """
        if not query or not query.strip():
            return ToolResult.fail("Search query cannot be empty")

        query = query.strip()
        logger.info(f"Looking up contact: {query}")

        try:
            # Determine if query is an email address
            is_email = "@" in query

            if is_email:
                # Search by email in connections
                contacts = self._search_by_email(query)
            else:
                # Search by name using People API search
                contacts = self._search_by_name(query, max_results)

            if not contacts:
                # Try to get basic info from the email if it looks like an email
                if is_email:
                    basic_contact = ContactInfo(
                        email=query,
                        name=self._extract_name_from_email(query),
                    )
                    return ToolResult.ok(
                        ContactSearchResults(query=query, contacts=[basic_contact]).to_dict(),
                        result_count=1,
                        source="email_parsed",
                    )
                return ToolResult.empty(f"No contacts found matching: {query}")

            results = ContactSearchResults(query=query, contacts=contacts[:max_results])
            return ToolResult.ok(
                results.to_dict(),
                result_count=len(contacts),
            )

        except HttpError as e:
            logger.error(f"People API error: {e}")
            return ToolResult.fail(f"People API error: {e.reason}")

    def _search_by_email(self, email: str) -> list[ContactInfo]:
        """Search contacts by email address."""
        contacts = []

        try:
            # Use searchContacts to find by email
            results = (
                self.service.people()
                .searchContacts(
                    query=email,
                    readMask="names,emailAddresses,phoneNumbers,organizations,photos",
                    pageSize=10,
                )
                .execute()
            )

            for result in results.get("results", []):
                person = result.get("person", {})
                contact = self._parse_person(person)
                if contact:
                    contacts.append(contact)

        except HttpError as e:
            if e.resp.status == 400:
                # searchContacts may not be available, try connections
                logger.debug("searchContacts not available, trying connections")
                contacts = self._search_connections_by_email(email)
            else:
                raise

        return contacts

    def _search_connections_by_email(self, email: str) -> list[ContactInfo]:
        """Search through user's connections for email."""
        contacts = []
        email_lower = email.lower()

        try:
            # Get all connections and filter by email
            results = (
                self.service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="names,emailAddresses,phoneNumbers,organizations,photos",
                    pageSize=100,
                )
                .execute()
            )

            for person in results.get("connections", []):
                emails = person.get("emailAddresses", [])
                for email_entry in emails:
                    if email_entry.get("value", "").lower() == email_lower:
                        contact = self._parse_person(person)
                        if contact:
                            contacts.append(contact)
                        break

        except HttpError as e:
            logger.warning(f"Failed to search connections: {e}")

        return contacts

    def _search_by_name(self, name: str, max_results: int) -> list[ContactInfo]:
        """Search contacts by name."""
        contacts = []

        try:
            results = (
                self.service.people()
                .searchContacts(
                    query=name,
                    readMask="names,emailAddresses,phoneNumbers,organizations,photos",
                    pageSize=max_results,
                )
                .execute()
            )

            for result in results.get("results", []):
                person = result.get("person", {})
                contact = self._parse_person(person)
                if contact:
                    contacts.append(contact)

        except HttpError as e:
            if e.resp.status == 400:
                # searchContacts may not be available, try connections
                logger.debug("searchContacts not available, trying connections")
                contacts = self._search_connections_by_name(name, max_results)
            else:
                raise

        return contacts

    def _search_connections_by_name(self, name: str, max_results: int) -> list[ContactInfo]:
        """Search through user's connections for name."""
        contacts = []
        name_lower = name.lower()

        try:
            results = (
                self.service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="names,emailAddresses,phoneNumbers,organizations,photos",
                    pageSize=100,
                )
                .execute()
            )

            for person in results.get("connections", []):
                names = person.get("names", [])
                for name_entry in names:
                    display_name = name_entry.get("displayName", "").lower()
                    given_name = name_entry.get("givenName", "").lower()
                    family_name = name_entry.get("familyName", "").lower()

                    if (
                        name_lower in display_name
                        or name_lower in given_name
                        or name_lower in family_name
                    ):
                        contact = self._parse_person(person)
                        if contact:
                            contacts.append(contact)
                        break

                if len(contacts) >= max_results:
                    break

        except HttpError as e:
            logger.warning(f"Failed to search connections: {e}")

        return contacts

    def _parse_person(self, person: dict[str, Any]) -> ContactInfo | None:
        """Parse a Person resource into ContactInfo."""
        # Get primary email
        emails = person.get("emailAddresses", [])
        if not emails:
            return None

        primary_email = emails[0].get("value", "")
        if not primary_email:
            return None

        # Get name
        names = person.get("names", [])
        name = names[0].get("displayName") if names else None

        # Get phone
        phones = person.get("phoneNumbers", [])
        phone = phones[0].get("value") if phones else None

        # Get organization
        orgs = person.get("organizations", [])
        organization = None
        job_title = None
        if orgs:
            organization = orgs[0].get("name")
            job_title = orgs[0].get("title")

        # Get photo
        photos = person.get("photos", [])
        photo_url = photos[0].get("url") if photos else None

        return ContactInfo(
            email=primary_email,
            name=name,
            phone=phone,
            organization=organization,
            job_title=job_title,
            photo_url=photo_url,
            resource_name=person.get("resourceName"),
        )

    def _extract_name_from_email(self, email: str) -> str | None:
        """Try to extract a name from email address."""
        local_part = email.split("@")[0]

        # Common patterns: john.doe, john_doe, johndoe
        if "." in local_part:
            parts = local_part.split(".")
            return " ".join(part.capitalize() for part in parts)
        if "_" in local_part:
            parts = local_part.split("_")
            return " ".join(part.capitalize() for part in parts)

        # If it looks like a name (not numbers), capitalize
        if local_part.isalpha():
            return local_part.capitalize()

        return None


# Singleton instance
contact_tool = ContactLookupTool()
