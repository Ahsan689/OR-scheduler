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

    # Operating-room working window (local hours) and on-time tolerance.
    or_day_start_hour: int = 8
    or_day_end_hour: int = 16
    on_time_grace_minutes: int = 5

    # Where the trained duration model is saved/loaded.
    model_path: str = "models/duration.joblib"

    # Scheduler (OR-Tools) parameters. Soft-goal weights are configurable.
    schedule_turnover_minutes: int = 25
    schedule_max_overtime_minutes: int = 300
    schedule_weight_overtime: int = 10
    schedule_weight_finish: int = 1
    schedule_time_limit_seconds: float = 10.0
    schedule_random_seed: int = 42


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
