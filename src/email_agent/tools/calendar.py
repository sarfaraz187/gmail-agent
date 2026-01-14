"""Calendar tool for checking availability."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
import logging

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from email_agent.gmail.auth import get_calendar_service
from email_agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class TimeSlot:
    """A time slot with start and end times."""

    start: datetime
    end: datetime

    def __str__(self) -> str:
        """Format time slot for display."""
        if self.start.date() == self.end.date():
            return f"{self.start.strftime('%a %b %d')}: {self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')}"
        return f"{self.start.strftime('%a %b %d %I:%M %p')} - {self.end.strftime('%a %b %d %I:%M %p')}"

    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "display": str(self),
            "duration_minutes": self.duration_minutes(),
        }


@dataclass
class CalendarAvailability:
    """Availability result from calendar check."""

    start_date: datetime
    end_date: datetime
    busy_slots: list[TimeSlot]
    free_slots: list[TimeSlot]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "busy_slots": [slot.to_dict() for slot in self.busy_slots],
            "free_slots": [slot.to_dict() for slot in self.free_slots],
            "summary": self.get_summary(),
        }

    def get_summary(self) -> str:
        """Get human-readable summary of availability."""
        if not self.free_slots:
            return "No available time slots found in the requested period."

        lines = ["Available times:"]
        for slot in self.free_slots[:5]:  # Limit to 5 slots
            lines.append(f"  - {slot}")

        if len(self.free_slots) > 5:
            lines.append(f"  ... and {len(self.free_slots) - 5} more slots")

        return "\n".join(lines)


class CalendarCheckTool(BaseTool):
    """Tool to check calendar availability."""

    def __init__(self, calendar_service: Resource | None = None):
        """Initialize with optional calendar service for testing."""
        self._service = calendar_service
        self._calendar_id = "primary"  # Use primary calendar by default

    @property
    def service(self) -> Resource:
        """Get calendar service, initializing if needed."""
        if self._service is None:
            self._service = get_calendar_service()
        return self._service

    @property
    def name(self) -> str:
        return "calendar_check"

    @property
    def description(self) -> str:
        return (
            "Check calendar availability for a given date range. "
            "Returns busy and free time slots. Use this when someone asks "
            "about meeting times or scheduling."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date/time in ISO format or relative (e.g., 'tomorrow', 'next Monday')",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date/time in ISO format. If not provided, defaults to end of start_date day.",
                },
                "min_duration_minutes": {
                    "type": "integer",
                    "description": "Minimum duration for free slots in minutes. Default: 30",
                    "default": 30,
                },
            },
            "required": ["start_date"],
        }

    def execute(
        self,
        start_date: str,
        end_date: str | None = None,
        min_duration_minutes: int = 30,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Check calendar availability.

        Args:
            start_date: Start date/time (ISO format or relative like "tomorrow")
            end_date: End date/time (ISO format). Defaults to end of start_date day.
            min_duration_minutes: Minimum duration for free slots (default: 30)

        Returns:
            ToolResult with CalendarAvailability data
        """
        try:
            # Parse dates
            start_dt = self._parse_date(start_date)
            if end_date:
                end_dt = self._parse_date(end_date)
            else:
                # Default to end of day
                end_dt = start_dt.replace(hour=23, minute=59, second=59)

            # Ensure start is before end
            if start_dt >= end_dt:
                return ToolResult.fail("Start date must be before end date")

            # Query free/busy
            body = {
                "timeMin": start_dt.isoformat(),
                "timeMax": end_dt.isoformat(),
                "items": [{"id": self._calendar_id}],
            }

            logger.info(f"Checking calendar availability from {start_dt} to {end_dt}")
            result = self.service.freebusy().query(body=body).execute()

            # Parse busy slots
            busy_periods = result.get("calendars", {}).get(self._calendar_id, {}).get("busy", [])
            busy_slots = [
                TimeSlot(
                    start=datetime.fromisoformat(period["start"].replace("Z", "+00:00")),
                    end=datetime.fromisoformat(period["end"].replace("Z", "+00:00")),
                )
                for period in busy_periods
            ]

            # Calculate free slots
            free_slots = self._calculate_free_slots(
                start_dt, end_dt, busy_slots, min_duration_minutes
            )

            availability = CalendarAvailability(
                start_date=start_dt,
                end_date=end_dt,
                busy_slots=busy_slots,
                free_slots=free_slots,
            )

            return ToolResult.ok(
                availability.to_dict(),
                slot_count=len(free_slots),
                busy_count=len(busy_slots),
            )

        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            return ToolResult.fail(f"Calendar API error: {e.reason}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            return ToolResult.fail(f"Invalid date format: {e}")

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        date_str = date_str.strip().lower()
        now = datetime.now()

        # Handle relative dates
        relative_dates = {
            "today": now.replace(hour=9, minute=0, second=0, microsecond=0),
            "tomorrow": (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
            "next week": (now + timedelta(weeks=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        }

        if date_str in relative_dates:
            return relative_dates[date_str]

        # Handle day names
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in date_str:
                current_day = now.weekday()
                days_ahead = i - current_day
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                if "next" in date_str:
                    days_ahead += 7
                target = now + timedelta(days=days_ahead)
                return target.replace(hour=9, minute=0, second=0, microsecond=0)

        # Handle "afternoon", "morning" modifiers
        if "afternoon" in date_str:
            base = self._parse_date(date_str.replace("afternoon", "").strip())
            return base.replace(hour=13, minute=0)
        if "morning" in date_str:
            base = self._parse_date(date_str.replace("morning", "").strip())
            return base.replace(hour=9, minute=0)

        # Try ISO format
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass

        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y",
            "%B %d",
            "%B %d, %Y",
            "%b %d",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # If no year in format, use current year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=now.year)
                return parsed.replace(hour=9, minute=0, second=0, microsecond=0)
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {date_str}")

    def _calculate_free_slots(
        self,
        start: datetime,
        end: datetime,
        busy_slots: list[TimeSlot],
        min_duration: int,
    ) -> list[TimeSlot]:
        """Calculate free slots between busy periods."""
        # Define working hours (9 AM - 6 PM)
        work_start_hour = 9
        work_end_hour = 18

        free_slots = []
        current = start

        # Sort busy slots by start time and normalize to naive datetimes for comparison
        sorted_busy = sorted(busy_slots, key=lambda x: x.start)

        # If no busy slots, the entire period is free (within work hours)
        if not sorted_busy:
            free_slot = self._create_work_hours_slot(
                start, end, work_start_hour, work_end_hour
            )
            if free_slot and free_slot.duration_minutes() >= min_duration:
                free_slots.append(free_slot)
            return free_slots

        for busy in sorted_busy:
            # Normalize busy slot times to naive for comparison
            busy_start = self._to_naive(busy.start)
            busy_end = self._to_naive(busy.end)

            # Check if there's free time before this busy slot
            if current < busy_start:
                free_slot = self._create_work_hours_slot(
                    current, busy_start, work_start_hour, work_end_hour
                )
                if free_slot and free_slot.duration_minutes() >= min_duration:
                    free_slots.append(free_slot)

            # Move current time to end of busy slot
            current = max(current, busy_end)

        # Check for free time after last busy slot
        if current < end:
            free_slot = self._create_work_hours_slot(
                current, end, work_start_hour, work_end_hour
            )
            if free_slot and free_slot.duration_minutes() >= min_duration:
                free_slots.append(free_slot)

        return free_slots

    def _to_naive(self, dt: datetime) -> datetime:
        """Convert timezone-aware datetime to naive (local time)."""
        if dt.tzinfo is not None:
            # Convert to local time and strip timezone
            return dt.replace(tzinfo=None)
        return dt

    def _create_work_hours_slot(
        self,
        start: datetime,
        end: datetime,
        work_start_hour: int,
        work_end_hour: int,
    ) -> TimeSlot | None:
        """Create a time slot constrained to work hours."""
        # Adjust start to work hours
        if start.hour < work_start_hour:
            start = start.replace(hour=work_start_hour, minute=0)
        if start.hour >= work_end_hour:
            return None

        # Adjust end to work hours
        if end.hour > work_end_hour or (end.hour == work_end_hour and end.minute > 0):
            end = end.replace(hour=work_end_hour, minute=0)
        if end.hour < work_start_hour:
            return None

        if start >= end:
            return None

        return TimeSlot(start=start, end=end)


# Singleton instance
calendar_tool = CalendarCheckTool()
