"""
Security utilities for the email agent.

Provides:
- Pub/Sub message authentication
- LLM prompt sanitization
- Input validation helpers
- Rate limiting configuration
"""

from email_agent.security.sanitization import (
    sanitize_for_prompt,
    sanitize_email_content,
    is_safe_firestore_id,
)
from email_agent.security.pubsub_auth import (
    verify_pubsub_token,
    PubSubAuthError,
)

__all__ = [
    "sanitize_for_prompt",
    "sanitize_email_content",
    "is_safe_firestore_id",
    "verify_pubsub_token",
    "PubSubAuthError",
]
