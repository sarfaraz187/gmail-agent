"""Tests for contacts lookup tool."""

from unittest.mock import MagicMock
import pytest
from googleapiclient.errors import HttpError

from email_agent.tools.contacts import (
    ContactLookupTool,
    ContactInfo,
    ContactSearchResults,
)
from email_agent.tools.base import ToolStatus


class TestContactInfo:
    """Tests for ContactInfo dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        contact = ContactInfo(
            email="john@example.com",
            name="John Doe",
            phone="+1-555-1234",
            organization="Acme Corp",
            job_title="Software Engineer",
        )
        result = contact.to_dict()

        assert result["email"] == "john@example.com"
        assert result["name"] == "John Doe"
        assert result["phone"] == "+1-555-1234"
        assert result["organization"] == "Acme Corp"
        assert result["job_title"] == "Software Engineer"

    def test_str_with_all_fields(self):
        """Test string representation with all fields."""
        contact = ContactInfo(
            email="john@example.com",
            name="John Doe",
            organization="Acme Corp",
            job_title="Software Engineer",
        )
        result = str(contact)

        assert "John Doe" in result
        assert "Software Engineer" in result
        assert "Acme Corp" in result
        assert "john@example.com" in result

    def test_str_minimal(self):
        """Test string representation with minimal fields."""
        contact = ContactInfo(email="john@example.com")
        result = str(contact)

        assert "john@example.com" in result

    def test_get_display_name_with_name(self):
        """Test display name with name set."""
        contact = ContactInfo(email="john@example.com", name="John Doe")
        assert contact.get_display_name() == "John Doe"

    def test_get_display_name_without_name(self):
        """Test display name falls back to email local part."""
        contact = ContactInfo(email="john@example.com")
        assert contact.get_display_name() == "john"


class TestContactSearchResults:
    """Tests for ContactSearchResults dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        results = ContactSearchResults(
            query="john",
            contacts=[
                ContactInfo(email="john@example.com", name="John Doe"),
            ],
        )
        result = results.to_dict()

        assert result["query"] == "john"
        assert len(result["contacts"]) == 1
        assert "summary" in result

    def test_get_summary_with_contacts(self):
        """Test summary with contacts found."""
        results = ContactSearchResults(
            query="john",
            contacts=[
                ContactInfo(email="john@example.com", name="John Doe"),
            ],
        )
        summary = results.get_summary()

        assert "Found 1 contact" in summary

    def test_get_summary_no_contacts(self):
        """Test summary with no contacts."""
        results = ContactSearchResults(query="nonexistent", contacts=[])
        summary = results.get_summary()

        assert "No contacts found" in summary


class TestContactLookupTool:
    """Tests for ContactLookupTool."""

    @pytest.fixture
    def mock_people_service(self):
        """Create mock People service."""
        service = MagicMock()
        return service

    @pytest.fixture
    def tool(self, mock_people_service):
        """Create tool with mock service."""
        return ContactLookupTool(people_service=mock_people_service)

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "lookup_contact"
        assert "contact" in tool.description.lower()
        assert "query" in tool.parameters_schema["properties"]
        assert "query" in tool.parameters_schema["required"]

    def test_execute_by_email_success(self, tool, mock_people_service):
        """Test successful lookup by email."""
        mock_people_service.people().searchContacts().execute.return_value = {
            "results": [
                {
                    "person": {
                        "resourceName": "people/123",
                        "names": [{"displayName": "John Doe"}],
                        "emailAddresses": [{"value": "john@example.com"}],
                        "phoneNumbers": [{"value": "+1-555-1234"}],
                        "organizations": [{"name": "Acme Corp", "title": "Engineer"}],
                    }
                }
            ]
        }

        result = tool.execute(query="john@example.com")

        assert result.success is True
        assert len(result.data["contacts"]) == 1
        assert result.data["contacts"][0]["name"] == "John Doe"

    def test_execute_by_name_success(self, tool, mock_people_service):
        """Test successful lookup by name."""
        mock_people_service.people().searchContacts().execute.return_value = {
            "results": [
                {
                    "person": {
                        "resourceName": "people/123",
                        "names": [{"displayName": "John Doe"}],
                        "emailAddresses": [{"value": "john@example.com"}],
                    }
                }
            ]
        }

        result = tool.execute(query="John")

        assert result.success is True
        assert len(result.data["contacts"]) == 1

    def test_execute_empty_query(self, tool):
        """Test with empty query."""
        result = tool.execute(query="")

        assert result.success is False
        assert "empty" in result.error.lower()

    def test_execute_whitespace_query(self, tool):
        """Test with whitespace-only query."""
        result = tool.execute(query="   ")

        assert result.success is False
        assert "empty" in result.error.lower()

    def test_execute_email_not_found_returns_parsed(self, tool, mock_people_service):
        """Test email not in contacts returns parsed info."""
        mock_people_service.people().searchContacts().execute.return_value = {
            "results": []
        }

        result = tool.execute(query="unknown@example.com")

        assert result.success is True
        assert result.data["contacts"][0]["email"] == "unknown@example.com"
        assert result.metadata.get("source") == "email_parsed"

    def test_execute_name_not_found(self, tool, mock_people_service):
        """Test name not in contacts returns empty."""
        mock_people_service.people().searchContacts().execute.return_value = {
            "results": []
        }

        result = tool.execute(query="nonexistent person xyz")

        assert result.status == ToolStatus.NO_RESULTS

    def test_parse_person_full(self, tool):
        """Test parsing person with all fields."""
        person = {
            "resourceName": "people/123",
            "names": [{"displayName": "John Doe"}],
            "emailAddresses": [{"value": "john@example.com"}],
            "phoneNumbers": [{"value": "+1-555-1234"}],
            "organizations": [{"name": "Acme Corp", "title": "Engineer"}],
            "photos": [{"url": "https://example.com/photo.jpg"}],
        }

        result = tool._parse_person(person)

        assert result is not None
        assert result.email == "john@example.com"
        assert result.name == "John Doe"
        assert result.phone == "+1-555-1234"
        assert result.organization == "Acme Corp"
        assert result.job_title == "Engineer"
        assert result.photo_url == "https://example.com/photo.jpg"

    def test_parse_person_minimal(self, tool):
        """Test parsing person with only email."""
        person = {
            "emailAddresses": [{"value": "john@example.com"}],
        }

        result = tool._parse_person(person)

        assert result is not None
        assert result.email == "john@example.com"
        assert result.name is None

    def test_parse_person_no_email(self, tool):
        """Test parsing person without email returns None."""
        person = {
            "names": [{"displayName": "John Doe"}],
        }

        result = tool._parse_person(person)

        assert result is None

    def test_extract_name_from_email_dot(self, tool):
        """Test extracting name from email with dot."""
        result = tool._extract_name_from_email("john.doe@example.com")
        assert result == "John Doe"

    def test_extract_name_from_email_underscore(self, tool):
        """Test extracting name from email with underscore."""
        result = tool._extract_name_from_email("john_doe@example.com")
        assert result == "John Doe"

    def test_extract_name_from_email_simple(self, tool):
        """Test extracting name from simple email."""
        result = tool._extract_name_from_email("john@example.com")
        assert result == "John"

    def test_extract_name_from_email_with_numbers(self, tool):
        """Test extracting name from email with numbers returns None."""
        result = tool._extract_name_from_email("user123@example.com")
        assert result is None

    def test_fallback_to_connections(self, tool, mock_people_service):
        """Test fallback to connections when searchContacts fails."""
        # First call fails with 400
        http_error = HttpError(
            resp=MagicMock(status=400),
            content=b"Bad Request",
        )
        mock_people_service.people().searchContacts().execute.side_effect = http_error

        # Connections fallback succeeds
        mock_people_service.people().connections().list().execute.return_value = {
            "connections": [
                {
                    "names": [{"displayName": "John Doe"}],
                    "emailAddresses": [{"value": "john@example.com"}],
                }
            ]
        }

        result = tool.execute(query="john@example.com")

        assert result.success is True
        # Verify connections.list was called
        mock_people_service.people().connections().list.assert_called()

    def test_max_results_parameter(self, tool, mock_people_service):
        """Test max_results limits results."""
        mock_people_service.people().searchContacts().execute.return_value = {
            "results": [
                {
                    "person": {
                        "names": [{"displayName": f"Person {i}"}],
                        "emailAddresses": [{"value": f"person{i}@example.com"}],
                    }
                }
                for i in range(10)
            ]
        }

        result = tool.execute(query="person", max_results=3)

        assert result.success is True
        assert len(result.data["contacts"]) == 3
