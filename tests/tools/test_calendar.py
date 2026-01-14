"""Tests for calendar tool."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

from email_agent.tools.calendar import (
    CalendarCheckTool,
    TimeSlot,
    CalendarAvailability,
)
from email_agent.tools.base import ToolStatus


class TestTimeSlot:
    """Tests for TimeSlot dataclass."""

    def test_duration_minutes(self):
        """Test duration calculation."""
        slot = TimeSlot(
            start=datetime(2026, 1, 15, 10, 0),
            end=datetime(2026, 1, 15, 11, 30),
        )
        assert slot.duration_minutes() == 90

    def test_str_same_day(self):
        """Test string representation for same-day slot."""
        slot = TimeSlot(
            start=datetime(2026, 1, 15, 10, 0),
            end=datetime(2026, 1, 15, 11, 0),
        )
        result = str(slot)
        assert "10:00 AM" in result
        assert "11:00 AM" in result

    def test_to_dict(self):
        """Test conversion to dictionary."""
        slot = TimeSlot(
            start=datetime(2026, 1, 15, 10, 0),
            end=datetime(2026, 1, 15, 11, 0),
        )
        result = slot.to_dict()
        assert "start" in result
        assert "end" in result
        assert "display" in result
        assert result["duration_minutes"] == 60


class TestCalendarAvailability:
    """Tests for CalendarAvailability dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        availability = CalendarAvailability(
            start_date=datetime(2026, 1, 15, 9, 0),
            end_date=datetime(2026, 1, 15, 18, 0),
            busy_slots=[],
            free_slots=[
                TimeSlot(datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 12, 0)),
            ],
        )
        result = availability.to_dict()
        assert "start_date" in result
        assert "end_date" in result
        assert "busy_slots" in result
        assert "free_slots" in result
        assert "summary" in result

    def test_get_summary_with_slots(self):
        """Test summary generation with free slots."""
        availability = CalendarAvailability(
            start_date=datetime(2026, 1, 15, 9, 0),
            end_date=datetime(2026, 1, 15, 18, 0),
            busy_slots=[],
            free_slots=[
                TimeSlot(datetime(2026, 1, 15, 9, 0), datetime(2026, 1, 15, 12, 0)),
            ],
        )
        summary = availability.get_summary()
        assert "Available times:" in summary

    def test_get_summary_no_slots(self):
        """Test summary generation with no free slots."""
        availability = CalendarAvailability(
            start_date=datetime(2026, 1, 15, 9, 0),
            end_date=datetime(2026, 1, 15, 18, 0),
            busy_slots=[],
            free_slots=[],
        )
        summary = availability.get_summary()
        assert "No available time slots" in summary


class TestCalendarCheckTool:
    """Tests for CalendarCheckTool."""

    @pytest.fixture
    def mock_calendar_service(self):
        """Create mock calendar service."""
        service = MagicMock()
        return service

    @pytest.fixture
    def tool(self, mock_calendar_service):
        """Create tool with mock service."""
        return CalendarCheckTool(calendar_service=mock_calendar_service)

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "calendar_check"
        assert "availability" in tool.description.lower()
        assert "start_date" in tool.parameters_schema["properties"]
        assert "start_date" in tool.parameters_schema["required"]

    def test_execute_success_no_busy(self, tool, mock_calendar_service):
        """Test successful execution with no busy slots."""
        mock_calendar_service.freebusy().query().execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": []
                }
            }
        }

        result = tool.execute(start_date="tomorrow")

        assert result.success is True
        assert "free_slots" in result.data
        assert len(result.data["free_slots"]) > 0

    def test_execute_success_with_busy(self, tool, mock_calendar_service):
        """Test successful execution with busy slots."""
        tomorrow = datetime.now() + timedelta(days=1)
        mock_calendar_service.freebusy().query().execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": tomorrow.replace(hour=10, minute=0).isoformat() + "Z",
                            "end": tomorrow.replace(hour=11, minute=0).isoformat() + "Z",
                        }
                    ]
                }
            }
        }

        result = tool.execute(start_date="tomorrow")

        assert result.success is True
        assert "busy_slots" in result.data
        assert len(result.data["busy_slots"]) == 1

    def test_execute_invalid_date_range(self, tool):
        """Test with end date before start date."""
        result = tool.execute(
            start_date="2026-01-20",
            end_date="2026-01-15",
        )

        assert result.success is False
        assert "before" in result.error.lower()

    def test_parse_date_today(self, tool):
        """Test parsing 'today'."""
        result = tool._parse_date("today")
        assert result.date() == datetime.now().date()

    def test_parse_date_tomorrow(self, tool):
        """Test parsing 'tomorrow'."""
        result = tool._parse_date("tomorrow")
        expected = (datetime.now() + timedelta(days=1)).date()
        assert result.date() == expected

    def test_parse_date_weekday(self, tool):
        """Test parsing day name like 'thursday'."""
        result = tool._parse_date("thursday")
        assert result.weekday() == 3  # Thursday is 3

    def test_parse_date_next_weekday(self, tool):
        """Test parsing 'next monday'."""
        result = tool._parse_date("next monday")
        assert result.weekday() == 0  # Monday is 0

    def test_parse_date_afternoon(self, tool):
        """Test parsing 'tomorrow afternoon'."""
        result = tool._parse_date("tomorrow afternoon")
        assert result.hour == 13

    def test_parse_date_morning(self, tool):
        """Test parsing 'tomorrow morning'."""
        result = tool._parse_date("tomorrow morning")
        assert result.hour == 9

    def test_parse_date_iso_format(self, tool):
        """Test parsing ISO format date."""
        result = tool._parse_date("2026-01-15T10:00:00")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_invalid(self, tool):
        """Test parsing invalid date raises error."""
        with pytest.raises(ValueError):
            tool._parse_date("not a date xyz123")

    def test_calculate_free_slots_empty_busy(self, tool):
        """Test free slot calculation with no busy slots."""
        start = datetime(2026, 1, 15, 9, 0)
        end = datetime(2026, 1, 15, 18, 0)

        free_slots = tool._calculate_free_slots(start, end, [], 30)

        assert len(free_slots) == 1
        assert free_slots[0].start.hour == 9
        assert free_slots[0].end.hour == 18

    def test_calculate_free_slots_with_busy(self, tool):
        """Test free slot calculation with busy slot in middle."""
        start = datetime(2026, 1, 15, 9, 0)
        end = datetime(2026, 1, 15, 18, 0)
        busy = [TimeSlot(datetime(2026, 1, 15, 12, 0), datetime(2026, 1, 15, 13, 0))]

        free_slots = tool._calculate_free_slots(start, end, busy, 30)

        assert len(free_slots) == 2  # Before and after the busy slot

    def test_work_hours_constraint(self, tool):
        """Test that free slots are constrained to work hours."""
        start = datetime(2026, 1, 15, 6, 0)  # Before work hours
        end = datetime(2026, 1, 15, 22, 0)  # After work hours

        free_slots = tool._calculate_free_slots(start, end, [], 30)

        # Should be constrained to 9-18
        assert free_slots[0].start.hour == 9
        assert free_slots[0].end.hour == 18

    def test_min_duration_filter(self, tool):
        """Test that slots shorter than min duration are filtered."""
        start = datetime(2026, 1, 15, 9, 0)
        end = datetime(2026, 1, 15, 18, 0)
        # Busy from 9:15 to 17:50 leaves only 15 min at start and 10 min at end
        busy = [TimeSlot(datetime(2026, 1, 15, 9, 15), datetime(2026, 1, 15, 17, 50))]

        free_slots = tool._calculate_free_slots(start, end, busy, 30)  # 30 min minimum

        assert len(free_slots) == 0  # Both slots < 30 min
