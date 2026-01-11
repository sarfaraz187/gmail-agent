"""Gmail integration module for the email agent."""

from email_agent.gmail.auth import get_gmail_credentials, get_gmail_service
from email_agent.gmail.client import EmailData, GmailClient, gmail_client
from email_agent.gmail.labels import GmailLabelManager, label_manager
from email_agent.gmail.watch import GmailWatchService, WatchResponse, watch_service

__all__ = [
    "get_gmail_credentials",
    "get_gmail_service",
    "EmailData",
    "GmailClient",
    "gmail_client",
    "GmailLabelManager",
    "label_manager",
    "GmailWatchService",
    "WatchResponse",
    "watch_service",
]
