"""
Gmail authentication module.

Loads credentials from Secret Manager in production (Cloud Run)
or from local token file in development.

Token Refresh Persistence:
When tokens are refreshed, they are automatically saved back to
Secret Manager (production) or local file (development) to ensure
fresh tokens are available on next cold start.
"""

import json
import logging
import os
from functools import lru_cache

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource

logger = logging.getLogger(__name__)

# Scopes required for the email agent
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]


def _load_from_secret_manager(secret_name: str, project_id: str) -> str:
    """Load a secret from Google Cloud Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def _load_from_local_file(file_path: str) -> str:
    """Load token from local file (for development)."""
    with open(file_path) as f:
        return f.read()


def _save_to_secret_manager(secret_name: str, project_id: str, token_json: str) -> None:
    """
    Save refreshed token to Google Cloud Secret Manager.

    Creates a new version of the secret with the updated token.
    """
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}/secrets/{secret_name}"

    client.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": token_json.encode("UTF-8")},
        }
    )
    logger.info(f"Saved refreshed token to Secret Manager: {secret_name}")


def _save_to_local_file(file_path: str, token_json: str) -> None:
    """Save refreshed token to local file (for development)."""
    with open(file_path, "w") as f:
        f.write(token_json)
    logger.info(f"Saved refreshed token to local file: {file_path}")


def _credentials_to_json(creds: Credentials) -> str:
    """
    Convert Credentials object to JSON string for storage.

    Args:
        creds: The Google OAuth2 Credentials object.

    Returns:
        JSON string with token data.
    """
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "universe_domain": "googleapis.com",
        "account": "",
        "expiry": creds.expiry.isoformat() + "Z" if creds.expiry else None,
    }
    return json.dumps(token_data)


@lru_cache(maxsize=1)
def get_gmail_credentials() -> Credentials:
    """
    Get Gmail API credentials.

    In production (Cloud Run): Loads from Secret Manager
    In development: Loads from local token.json file

    When tokens are refreshed, they are automatically persisted back
    to storage to ensure fresh tokens on next cold start.

    Returns:
        Google OAuth2 Credentials object
    """
    # Check if running in Cloud Run (GCP sets these env vars)
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    is_cloud_run = os.getenv("K_SERVICE") is not None
    local_token_path = os.getenv("GMAIL_TOKEN_PATH", "scripts/token.json")

    if is_cloud_run and project_id:
        # Production: Load from Secret Manager
        token_json = _load_from_secret_manager("gmail-refresh-token", project_id)
    else:
        # Development: Load from local file
        if not os.path.exists(local_token_path):
            raise FileNotFoundError(
                f"Token file not found at {local_token_path}. "
                "Run 'python scripts/gmail_auth.py' to authenticate."
            )
        token_json = _load_from_local_file(local_token_path)

    # Parse token JSON
    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Refresh if expired and persist the new token
    if creds.expired and creds.refresh_token:
        logger.info("Access token expired, refreshing...")
        creds.refresh(Request())

        # Persist refreshed token back to storage
        try:
            refreshed_token_json = _credentials_to_json(creds)
            if is_cloud_run and project_id:
                _save_to_secret_manager("gmail-refresh-token", project_id, refreshed_token_json)
            else:
                _save_to_local_file(local_token_path, refreshed_token_json)
        except Exception as e:
            # Log but don't fail - the in-memory token still works
            logger.warning(f"Failed to persist refreshed token: {e}")

    return creds


@lru_cache(maxsize=1)
def get_gmail_service() -> Resource:
    """
    Get authenticated Gmail API service.

    Returns:
        Gmail API Resource object
    """
    creds = get_gmail_credentials()
    return build("gmail", "v1", credentials=creds)


@lru_cache(maxsize=1)
def get_calendar_service() -> Resource:
    """
    Get authenticated Calendar API service.

    Returns:
        Calendar API Resource object
    """
    creds = get_gmail_credentials()
    return build("calendar", "v3", credentials=creds)


@lru_cache(maxsize=1)
def get_people_service() -> Resource:
    """
    Get authenticated People API service (for contacts).

    Returns:
        People API Resource object
    """
    creds = get_gmail_credentials()
    return build("people", "v1", credentials=creds)
