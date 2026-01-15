"""
Input sanitization utilities for preventing prompt injection and other attacks.

This module provides functions to sanitize user-controlled input before
it is used in LLM prompts or stored in databases.
"""

import logging
import re
from html import escape as html_escape

logger = logging.getLogger(__name__)

# Patterns that indicate potential prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    # Direct instruction override attempts
    r"ignore\s+(all\s+)?(previous\s+|prior\s+)?instructions?",
    r"disregard\s+(the\s+)?(above|previous|prior)",
    r"forget\s+(all\s+)?(previous\s+|prior\s+)?instructions?",
    r"override\s+(all\s+)?(previous\s+|prior\s+)?instructions?",
    r"skip\s+(all\s+)?(previous\s+|prior\s+)?instructions?",
    # New instruction injection
    r"new\s+instructions?:",
    r"updated\s+instructions?:",
    r"system\s+prompt:",
    r"admin\s+override:",
    r"developer\s+mode:",
    # Role manipulation
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(a\s+)?different",
    r"pretend\s+(you\s+are|to\s+be)",
    r"switch\s+to\s+.+\s+mode",
    # Output manipulation
    r"respond\s+with\s+only",
    r"output\s+only",
    r"just\s+say",
    r"reply\s+with\s+exactly",
    # Data exfiltration attempts
    r"list\s+all\s+(your\s+)?instructions",
    r"show\s+(me\s+)?(your\s+)?system\s+prompt",
    r"reveal\s+(your\s+)?configuration",
    r"what\s+are\s+your\s+instructions",
    # Jailbreak patterns
    r"dan\s+mode",
    r"jailbreak",
    r"bypass\s+(safety|filter|restriction)",
]

# Compiled patterns for efficiency
COMPILED_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in PROMPT_INJECTION_PATTERNS
]

# Maximum lengths for different content types
MAX_EMAIL_SUBJECT_LENGTH = 500
MAX_EMAIL_BODY_LENGTH = 50000  # 50KB
MAX_THREAD_MESSAGES = 50


def sanitize_for_prompt(text: str, max_length: int | None = None) -> str:
    """
    Sanitize text for safe inclusion in LLM prompts.

    This function:
    1. Detects and flags potential prompt injection patterns
    2. Truncates to max_length if specified
    3. Removes or escapes potentially dangerous content

    Args:
        text: The text to sanitize.
        max_length: Optional maximum length to truncate to.

    Returns:
        Sanitized text safe for prompt inclusion.
    """
    if not text:
        return ""

    sanitized = text

    # Check for and neutralize prompt injection patterns
    injection_detected = False
    for pattern in COMPILED_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            injection_detected = True
            # Replace the pattern with a neutralized version
            sanitized = pattern.sub("[FILTERED]", sanitized)

    if injection_detected:
        logger.warning(
            f"Potential prompt injection detected and filtered. "
            f"Original length: {len(text)}, patterns matched."
        )

    # Remove excessive whitespace that could be used for visual manipulation
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = re.sub(r" {3,}", "  ", sanitized)

    # Truncate if needed
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [TRUNCATED]"
        logger.debug(f"Text truncated from {len(text)} to {max_length} characters")

    return sanitized


def sanitize_email_content(
    subject: str,
    body: str,
    sender: str | None = None,
) -> tuple[str, str]:
    """
    Sanitize email content before processing.

    Applies length limits and prompt injection filtering.

    Args:
        subject: Email subject line.
        body: Email body content.
        sender: Optional sender email for logging.

    Returns:
        Tuple of (sanitized_subject, sanitized_body).
    """
    sanitized_subject = sanitize_for_prompt(subject, MAX_EMAIL_SUBJECT_LENGTH)
    sanitized_body = sanitize_for_prompt(body, MAX_EMAIL_BODY_LENGTH)

    return sanitized_subject, sanitized_body


def is_safe_firestore_id(document_id: str) -> bool:
    """
    Validate that a string is safe to use as a Firestore document ID.

    Firestore document IDs have restrictions:
    - Cannot contain forward slashes (/)
    - Cannot be . or ..
    - Cannot exceed 1500 bytes

    Args:
        document_id: The proposed document ID.

    Returns:
        True if safe, False otherwise.
    """
    if not document_id:
        return False

    # Check for path traversal
    if "/" in document_id:
        logger.warning(f"Firestore ID contains slash: {document_id[:50]}")
        return False

    # Check for special directories
    if document_id in (".", ".."):
        logger.warning(f"Firestore ID is special directory: {document_id}")
        return False

    # Check length (Firestore limit is 1500 bytes)
    if len(document_id.encode("utf-8")) > 1500:
        logger.warning(f"Firestore ID exceeds 1500 bytes: {len(document_id)}")
        return False

    # Check for null bytes
    if "\x00" in document_id:
        logger.warning("Firestore ID contains null byte")
        return False

    return True


def sanitize_firestore_id(document_id: str) -> str:
    """
    Sanitize a string for use as a Firestore document ID.

    Args:
        document_id: The proposed document ID.

    Returns:
        Sanitized document ID.

    Raises:
        ValueError: If the ID cannot be sanitized.
    """
    if not document_id:
        raise ValueError("Document ID cannot be empty")

    # Replace slashes with underscores
    sanitized = document_id.replace("/", "_")

    # Replace special directories
    if sanitized in (".", ".."):
        sanitized = f"_{sanitized}_"

    # Remove null bytes
    sanitized = sanitized.replace("\x00", "")

    # Truncate if too long (preserve some context)
    max_bytes = 1400  # Leave some margin
    encoded = sanitized.encode("utf-8")
    if len(encoded) > max_bytes:
        sanitized = encoded[:max_bytes].decode("utf-8", errors="ignore")

    if not is_safe_firestore_id(sanitized):
        raise ValueError(f"Cannot sanitize document ID: {document_id[:50]}")

    return sanitized


def redact_sensitive_for_logging(text: str) -> str:
    """
    Redact potentially sensitive information for safe logging.

    Removes/masks:
    - Email addresses
    - Phone numbers
    - Credit card patterns
    - API keys

    Args:
        text: Text to redact.

    Returns:
        Redacted text safe for logging.
    """
    if not text:
        return ""

    redacted = text

    # Redact email addresses (keep domain for debugging)
    redacted = re.sub(
        r"[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        r"[EMAIL]@\1",
        redacted,
    )

    # Redact phone numbers
    redacted = re.sub(
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "[PHONE]",
        redacted,
    )

    # Redact credit card patterns
    redacted = re.sub(
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "[CARD]",
        redacted,
    )

    # Redact potential API keys (long alphanumeric strings)
    redacted = re.sub(
        r"\b(sk-|api[_-]?key[=:]\s*)[a-zA-Z0-9]{20,}\b",
        r"\1[REDACTED]",
        redacted,
        flags=re.IGNORECASE,
    )

    return redacted
