"""Gmail integration module for the email agent."""

from email_agent.gmail.auth import get_gmail_credentials, get_gmail_service

__all__ = ["get_gmail_credentials", "get_gmail_service"]
