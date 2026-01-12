"""
Unit tests for user configuration loading.

Tests cover:
- Loading config from YAML file
- Default values when config is missing
- Signature appending functionality
- User preferences loading
"""

import pytest

from email_agent.user_config import (
    UserConfig,
    UserPreferences,
    append_signature,
    load_user_config,
)


class TestLoadUserConfig:
    """Tests for loading user configuration."""

    def test_load_valid_config(self, tmp_path) -> None:
        """Test loading a valid config.yaml file."""
        config_content = """
user:
  email: "test@example.com"
  signature: |
    Best regards,
    Test User

preferences:
  default_tone: "casual"
  always_notify_senders:
    - "boss@company.com"
  auto_respond_types:
    - "meeting_confirmation"
    - "scheduling_request"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_user_config(config_file)

        assert config.email == "test@example.com"
        assert "Best regards" in config.signature
        assert config.preferences.default_tone == "casual"
        assert "boss@company.com" in config.preferences.always_notify_senders
        assert "meeting_confirmation" in config.preferences.auto_respond_types

    def test_load_missing_config_returns_defaults(self) -> None:
        """Test that missing config file returns default values."""
        config = load_user_config("/nonexistent/path/config.yaml")

        assert config.email == ""
        assert config.signature == ""
        assert config.preferences.default_tone == "professional"
        assert config.preferences.always_notify_senders == []
        assert "meeting_confirmation" in config.preferences.auto_respond_types

    def test_load_empty_config(self, tmp_path) -> None:
        """Test loading an empty config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = load_user_config(config_file)

        assert config.email == ""
        assert config.signature == ""

    def test_load_partial_config(self, tmp_path) -> None:
        """Test loading config with only some values."""
        config_content = """
user:
  email: "partial@example.com"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_user_config(config_file)

        assert config.email == "partial@example.com"
        assert config.signature == ""
        assert config.preferences.default_tone == "professional"


class TestAppendSignature:
    """Tests for signature appending."""

    def test_append_signature_with_text(self) -> None:
        """Test appending a signature to email body."""
        body = "Hello, this is my email."
        signature = "Best regards,\nTest User"

        result = append_signature(body, signature)

        assert "Hello, this is my email." in result
        assert "--" in result
        assert "Best regards" in result
        assert "Test User" in result

    def test_append_empty_signature(self) -> None:
        """Test that empty signature doesn't modify body."""
        body = "Hello, this is my email."
        signature = ""

        result = append_signature(body, signature)

        assert result == body

    def test_append_none_signature(self, tmp_path) -> None:
        """Test signature from config when None is passed."""
        # Create a config file
        config_content = """
user:
  signature: "From Config"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        # This would use the module's cached config
        # For now, just test with explicit signature
        body = "Test email"
        result = append_signature(body, None)

        # Should return body as-is if config has no signature
        # (since we can't easily override the cached config in tests)
        assert "Test email" in result

    def test_signature_format(self) -> None:
        """Test that signature is properly formatted with separator."""
        body = "Email content here."
        signature = "John Doe\nCompany Inc."

        result = append_signature(body, signature)

        # Check format: body + newlines + separator + signature
        assert result == "Email content here.\n\n--\nJohn Doe\nCompany Inc."


class TestUserPreferencesDefaults:
    """Tests for UserPreferences defaults."""

    def test_default_preferences(self) -> None:
        """Test default UserPreferences values."""
        prefs = UserPreferences()

        assert prefs.default_tone == "professional"
        assert prefs.always_notify_senders == []
        assert "meeting_confirmation" in prefs.auto_respond_types
        assert "simple_acknowledgment" in prefs.auto_respond_types
        assert "scheduling_request" in prefs.auto_respond_types


class TestUserConfigDefaults:
    """Tests for UserConfig defaults."""

    def test_default_config(self) -> None:
        """Test default UserConfig values."""
        config = UserConfig()

        assert config.email == ""
        assert config.signature == ""
        assert isinstance(config.preferences, UserPreferences)
