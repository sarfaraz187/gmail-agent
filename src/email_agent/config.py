"""Application configuration using Pydantic settings."""

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
    app_name: str = "Gmail AI Draft Agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # LLM Settings
    openai_model: str = "gpt-4o"
    max_tokens: int = 500
    temperature: float = 0.7


settings = Settings()
