"""Test that the Alembic migration builds the full schema."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_upgrade_head_creates_all_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "migration_test.db"
    url = f"sqlite:///{db_file}"

    # env.py reads the URL from settings; point it at a throwaway SQLite DB.
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(cfg, "head")

        engine = create_engine(url)
        actual_tables = set(inspect(engine).get_table_names())
        engine.dispose()
    finally:
        get_settings.cache_clear()

    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    missing = expected_tables - actual_tables
    assert not missing, f"migration did not create: {missing}"
    # Alembic also records its own version table.
    assert "alembic_version" in actual_tables
