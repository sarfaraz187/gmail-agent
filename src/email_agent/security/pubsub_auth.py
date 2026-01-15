"""
Pub/Sub push message authentication.

Verifies that incoming webhook requests actually came from Google Pub/Sub
by validating the JWT bearer token in the Authorization header.

See: https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions
"""

import logging
import os
from functools import lru_cache

from cachetools import TTLCache
from google.auth import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

# Cache for verified tokens (5 minute TTL, max 1000 entries)
_token_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)


class PubSubAuthError(Exception):
    """Raised when Pub/Sub authentication fails."""

    pass


@lru_cache(maxsize=1)
def _get_expected_audience() -> str:
    """
    Get the expected audience for Pub/Sub tokens.

    In Cloud Run, this should be the service URL.
    Can be overridden with PUBSUB_AUDIENCE env var.

    Returns:
        The expected audience URL.
    """
    # Allow override via environment variable
    if audience := os.getenv("PUBSUB_AUDIENCE"):
        return audience

    # In Cloud Run, construct from service URL
    service_name = os.getenv("K_SERVICE")
    region = os.getenv("CLOUD_RUN_REGION", "europe-west1")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

    if service_name and project_id:
        return f"https://{service_name}-{project_id}.{region}.run.app"

    # Fallback for local development
    return os.getenv("SERVICE_URL", "http://localhost:8000")


@lru_cache(maxsize=1)
def _get_expected_email() -> str | None:
    """
    Get the expected service account email for Pub/Sub.

    Returns:
        Expected email or None to skip email verification.
    """
    return os.getenv("PUBSUB_SERVICE_ACCOUNT_EMAIL")


def verify_pubsub_token(
    authorization_header: str | None,
    skip_in_development: bool = True,
) -> dict:
    """
    Verify the Pub/Sub push authentication token.

    Pub/Sub sends a JWT bearer token in the Authorization header.
    This function verifies:
    1. The token is properly signed by Google
    2. The token is not expired
    3. The audience matches our service URL
    4. Optionally, the email matches our expected service account

    Args:
        authorization_header: The Authorization header value (e.g., "Bearer <token>").
        skip_in_development: If True, skip verification in local development.

    Returns:
        The decoded token claims if valid.

    Raises:
        PubSubAuthError: If verification fails.
    """
    # Check if running in Cloud Run
    is_cloud_run = os.getenv("K_SERVICE") is not None

    # In development, optionally skip verification
    if not is_cloud_run and skip_in_development:
        logger.debug("Skipping Pub/Sub auth verification in development")
        return {"development_mode": True}

    # Verify Authorization header is present
    if not authorization_header:
        raise PubSubAuthError("Missing Authorization header")

    # Parse Bearer token
    if not authorization_header.startswith("Bearer "):
        raise PubSubAuthError("Invalid Authorization header format")

    token = authorization_header[7:]  # Remove "Bearer " prefix

    if not token:
        raise PubSubAuthError("Empty bearer token")

    # Check cache first
    if token in _token_cache:
        logger.debug("Using cached token verification")
        return _token_cache[token]

    try:
        # Verify the token with Google
        audience = _get_expected_audience()
        logger.debug(f"Verifying token with audience: {audience}")

        # Use Google's ID token verification
        # This handles:
        # - Signature verification against Google's public keys
        # - Expiration checking
        # - Audience verification
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=audience,
        )

        # Optionally verify the service account email
        expected_email = _get_expected_email()
        if expected_email:
            token_email = claims.get("email", "")
            if token_email != expected_email:
                raise PubSubAuthError(
                    f"Token email mismatch: expected {expected_email}, got {token_email}"
                )

        # Cache the successful verification
        _token_cache[token] = claims

        logger.info("Pub/Sub token verified successfully")
        return claims

    except ValueError as e:
        # google.oauth2.id_token raises ValueError for invalid tokens
        logger.warning(f"Pub/Sub token verification failed: {e}")
        raise PubSubAuthError(f"Invalid token: {e}")

    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise PubSubAuthError(f"Token verification failed: {e}")


def is_pubsub_auth_enabled() -> bool:
    """
    Check if Pub/Sub authentication is enabled.

    Returns:
        True if running in Cloud Run or PUBSUB_AUTH_ENABLED is set.
    """
    is_cloud_run = os.getenv("K_SERVICE") is not None
    force_enabled = os.getenv("PUBSUB_AUTH_ENABLED", "").lower() == "true"

    return is_cloud_run or force_enabled
