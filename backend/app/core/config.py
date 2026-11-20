"""Application configuration.

All settings come from environment variables (or a local ``.env`` file).
No secrets or environment-specific URLs are hardcoded.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ORFlow"
    environment: str = "development"
    debug: bool = False

    # Database connection string, e.g.
    # postgresql+psycopg://orflow:orflow@localhost:5432/orflow
    database_url: str = "postgresql+psycopg://orflow:orflow@localhost:5432/orflow"

    # Comma-separated list of allowed CORS origins.
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
