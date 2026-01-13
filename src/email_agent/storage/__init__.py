"""Storage module for persistent state management."""

from email_agent.storage.history_tracker import HistoryTracker, history_tracker
from email_agent.storage.contact_memory import (
    ContactMemoryStore,
    ContactMemory,
    ContactStyle,
    ContactTopic,
    contact_memory_store,
)

__all__ = [
    "HistoryTracker",
    "history_tracker",
    "ContactMemoryStore",
    "ContactMemory",
    "ContactStyle",
    "ContactTopic",
    "contact_memory_store",
]
