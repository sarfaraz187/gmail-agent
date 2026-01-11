#!/usr/bin/env python3
"""
One-time setup script to create Gmail labels for the email agent.

This script creates the following labels in your Gmail account:
- "Agent Respond" (Green)  - Apply this to emails you want the agent to handle
- "Agent Done" (Blue)      - Agent adds this after processing
- "Agent Pending" (Orange) - Agent adds this when your decision is needed

Usage:
    python scripts/setup_gmail_labels.py

Prerequisites:
    - Run `python scripts/gmail_auth.py` first to authenticate
    - Ensure token.json exists in scripts/ directory
"""

import sys
from pathlib import Path

# Add src to path so we can import email_agent
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def main() -> None:
    """Create Gmail labels for the email agent."""
    print("=" * 60)
    print("Gmail Labels Setup for Email Agent")
    print("=" * 60)
    print()

    # Import here after path setup
    from email_agent.gmail.auth import get_gmail_service
    from email_agent.gmail.labels import GmailLabelManager

    # Check if authenticated
    try:
        service = get_gmail_service()
        print("[OK] Connected to Gmail API")
    except FileNotFoundError as e:
        print("[ERROR] Not authenticated!")
        print(f"       {e}")
        print()
        print("Run this first: python scripts/gmail_auth.py")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to connect to Gmail: {e}")
        sys.exit(1)

    # Create label manager
    manager = GmailLabelManager(gmail_service=service)

    print()
    print("Creating labels...")
    print("-" * 40)

    # Create/verify labels
    try:
        labels = manager.ensure_labels_exist()
    except Exception as e:
        print(f"[ERROR] Failed to create labels: {e}")
        sys.exit(1)

    # Print results
    print()
    print("Label Summary:")
    print("-" * 40)

    for name, label_id in labels.items():
        color = manager.LABEL_COLORS.get(name, {})
        bg_color = color.get("backgroundColor", "default")
        print(f"  {name}")
        print(f"    ID: {label_id}")
        print(f"    Color: {bg_color}")
        print()

    print("=" * 60)
    print("Setup complete!")
    print()
    print("Next steps:")
    print("  1. Open Gmail in your browser")
    print("  2. Find an email you want the agent to handle")
    print("  3. Apply the 'Agent Respond' label to it")
    print("  4. The agent will process it when running")
    print("=" * 60)


if __name__ == "__main__":
    main()
