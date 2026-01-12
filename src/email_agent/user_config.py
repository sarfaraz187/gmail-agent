"""
User configuration from config.yaml.

This module loads user preferences, signature, and other settings
from the config.yaml file. These are separate from environment-based
settings in config.py.

config.yaml is for:
- User email signature
- Tone preferences
- Always-notify senders list
- Auto-respond email types

.env is for:
- API keys (secrets)
- GCP settings
- Feature flags
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache

import yaml

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass
class UserPreferences:
    """User preferences from config.yaml."""

    default_tone: str = "professional"
    always_notify_senders: list[str] = field(default_factory=list)
    auto_respond_types: list[str] = field(default_factory=lambda: [
        "meeting_confirmation",
        "simple_acknowledgment",
        "scheduling_request",
    ])


@dataclass
class UserConfig:
    """Complete user configuration from config.yaml."""

    email: str = ""
    signature: str = ""
    preferences: UserPreferences = field(default_factory=UserPreferences)


def load_user_config(config_path: Path | str | None = None) -> UserConfig:
    """
    Load user configuration from config.yaml.

    Args:
        config_path: Path to config.yaml. Uses default if None.

    Returns:
        UserConfig with loaded or default values.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return UserConfig()

    try:
        raw_config = yaml.safe_load(config_path.read_text())

        if raw_config is None:
            return UserConfig()

        user_section = raw_config.get("user", {})
        prefs_section = raw_config.get("preferences", {})

        preferences = UserPreferences(
            default_tone=prefs_section.get("default_tone", "professional"),
            always_notify_senders=prefs_section.get("always_notify_senders", []),
            auto_respond_types=prefs_section.get("auto_respond_types", [
                "meeting_confirmation",
                "simple_acknowledgment",
                "scheduling_request",
            ]),
        )

        return UserConfig(
            email=user_section.get("email", ""),
            signature=user_section.get("signature", "").strip(),
            preferences=preferences,
        )

    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")
        return UserConfig()


@lru_cache(maxsize=1)
def get_user_config() -> UserConfig:
    """
    Get cached user configuration.

    Returns:
        UserConfig loaded from config.yaml (cached).
    """
    return load_user_config()


def append_signature(body: str, signature: str | None = None) -> str:
    """
    Append email signature to body.

    Args:
        body: The email body text.
        signature: Optional signature. Uses config if None.

    Returns:
        Body with signature appended (if signature exists).
    """
    if signature is None:
        config = get_user_config()
        signature = config.signature

    if not signature:
        return body

    return f"{body}\n\n--\n{signature}"


# Module-level config instance for easy access
user_config = get_user_config()
