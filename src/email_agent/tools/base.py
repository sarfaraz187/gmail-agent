"""Base tool interface for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import logging

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """Status of tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    NOT_FOUND = "not_found"
    NO_RESULTS = "no_results"


@dataclass
class ToolResult:
    """Result from tool execution."""

    status: ToolStatus
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if tool execution was successful."""
        return self.status == ToolStatus.SUCCESS

    @classmethod
    def ok(cls, data: Any, **metadata: Any) -> "ToolResult":
        """Create a successful result."""
        return cls(status=ToolStatus.SUCCESS, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> "ToolResult":
        """Create a failed result."""
        return cls(status=ToolStatus.ERROR, error=error, metadata=metadata)

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "ToolResult":
        """Create a not found result."""
        return cls(status=ToolStatus.NOT_FOUND, error=message)

    @classmethod
    def empty(cls, message: str = "No results found") -> "ToolResult":
        """Create an empty result."""
        return cls(status=ToolStatus.NO_RESULTS, data=[], error=message)


class BaseTool(ABC):
    """Base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used for invocation."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM context."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def validate_params(self, **kwargs: Any) -> tuple[bool, str | None]:
        """Validate parameters against schema. Returns (is_valid, error_message)."""
        schema = self.parameters_schema
        required = schema.get("required", [])

        for param in required:
            if param not in kwargs or kwargs[param] is None:
                return False, f"Missing required parameter: {param}"

        return True, None

    def __call__(self, **kwargs: Any) -> ToolResult:
        """Allow tool to be called directly."""
        is_valid, error = self.validate_params(**kwargs)
        if not is_valid:
            return ToolResult.fail(error or "Invalid parameters")

        try:
            return self.execute(**kwargs)
        except Exception as e:
            logger.exception(f"Tool {self.name} failed: {e}")
            return ToolResult.fail(str(e))
