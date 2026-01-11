#!/usr/bin/env python3
"""
One-time OAuth2 authentication script for Gmail API.

Run this locally to get a refresh token, then store it in Secret Manager.

Usage:
    1. Download OAuth credentials from GCP Console as 'credentials.json'
    2. Place 'credentials.json' in this directory
    3. Run: python scripts/gmail_auth.py
    4. Browser will open for Google login
    5. Token will be saved to 'token.json'
    6. Upload to Secret Manager:
       gcloud secrets create gmail-refresh-token --data-file=token.json
"""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for the email agent
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"


def main() -> None:
    """Run OAuth2 flow to get and save credentials."""
    creds = None

    # Check for existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        print(f"Found existing token at {TOKEN_FILE}")

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: {CREDENTIALS_FILE} not found!")
                print("\nTo get credentials.json:")
                print("1. Go to https://console.cloud.google.com/apis/credentials")
                print("2. Click 'Create Credentials' > 'OAuth client ID'")
                print("3. Select 'Desktop app' as application type")
                print("4. Download the JSON file")
                print(f"5. Save it as: {CREDENTIALS_FILE}")
                return

            print("Starting OAuth2 flow...")
            print("A browser window will open for Google login.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print(f"\nToken saved to: {TOKEN_FILE}")

    # Display token info
    print("\n" + "=" * 50)
    print("SUCCESS! OAuth2 authentication complete.")
    print("=" * 50)

    # Show the refresh token (for Secret Manager)
    token_data = json.loads(TOKEN_FILE.read_text())
    print(f"\nRefresh Token: {token_data.get('refresh_token', 'N/A')[:50]}...")
    print(f"Scopes: {', '.join(token_data.get('scopes', []))}")

    print("\n" + "=" * 50)
    print("NEXT STEPS:")
    print("=" * 50)
    print("\n1. Upload token to Secret Manager:")
    print(f"   gcloud secrets create gmail-refresh-token --data-file={TOKEN_FILE}")
    print("\n   Or if secret already exists:")
    print(f"   gcloud secrets versions add gmail-refresh-token --data-file={TOKEN_FILE}")
    print("\n2. Delete local token file (optional but recommended):")
    print(f"   rm {TOKEN_FILE}")


if __name__ == "__main__":
    main()
