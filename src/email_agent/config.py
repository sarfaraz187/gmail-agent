"""Application configuration using Pydantic settings."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI
    openai_api_key: str

    # Application
    app_name: str = "Gmail AI Agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # LLM Settings (default to mini for cost efficiency, override with OPENAI_MODEL env var)
    openai_model: str = "gpt-4o-mini"
    max_tokens: int = 500
    temperature: float = 0.7

    # GCP Settings
    gcp_project_id: str | None = None  # Auto-detected in Cloud Run via env var
    gcp_region: str = "europe-west1"

    # Pub/Sub Settings
    pubsub_topic: str = "gmail-agent"

    # Firestore Settings
    firestore_collection: str = "email_agent_state"

    # Gmail Label Names
    label_agent_respond: str = "Agent Respond"
    label_agent_done: str = "Agent Done"
    label_agent_pending: str = "Agent Pending"

    @property
    def project_id(self) -> str | None:
        """Get GCP project ID from settings or environment."""
        return (
            self.gcp_project_id
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT")
        )


settings = Settings()
