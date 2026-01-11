"""
Gmail authentication module.

Loads credentials from Secret Manager in production (Cloud Run)
or from local token file in development.
"""

import json
import os
from functools import lru_cache

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource

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


@lru_cache(maxsize=1)
def get_gmail_credentials() -> Credentials:
    """
    Get Gmail API credentials.

    In production (Cloud Run): Loads from Secret Manager
    In development: Loads from local token.json file

    Returns:
        Google OAuth2 Credentials object
    """
    # Check if running in Cloud Run (GCP sets these env vars)
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    is_cloud_run = os.getenv("K_SERVICE") is not None

    if is_cloud_run and project_id:
        # Production: Load from Secret Manager
        token_json = _load_from_secret_manager("gmail-refresh-token", project_id)
    else:
        # Development: Load from local file
        local_token_path = os.getenv("GMAIL_TOKEN_PATH", "scripts/token.json")
        if not os.path.exists(local_token_path):
            raise FileNotFoundError(
                f"Token file not found at {local_token_path}. "
                "Run 'python scripts/gmail_auth.py' to authenticate."
            )
        token_json = _load_from_local_file(local_token_path)

    # Parse token JSON
    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

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
