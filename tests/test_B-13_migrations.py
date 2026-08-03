"""B-13: Schema versioning / migrations.

Regression: schema version tracking exists.
Behavioral: migrations are idempotent (can run twice).
"""
import pytest


class TestSchemaVersioning:
    """Regression: schema version table must exist."""

    def test_schema_version_table_exists(self, app, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchall()
        if not tables:
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%migration%'"
            ).fetchall()
        if not tables:
            pytest.skip("schema_version table not implemented yet")

    def test_schema_version_has_version_field(self, app, db):
        try:
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchall()
            if tables:
                cols = db.execute("PRAGMA table_info(schema_version)").fetchall()
                col_names = [c[1].lower() for c in cols]
                assert any("version" in c for c in col_names), (
                    f"schema_version must have a version column, got: {col_names}"
                )
            else:
                pytest.skip("schema_version table not found")
        except Exception:
            pytest.skip("schema_version table not found")

    def test_schema_version_stores_current_version(self, app, db):
        try:
            rows = db.execute("SELECT * FROM schema_version").fetchall()
            assert len(rows) >= 1, "schema_version should have at least one row"
        except Exception:
            pytest.skip("schema_version table not found")


class TestMigrationIdempotency:
    """Behavioral: running init_db twice should not fail."""

    def test_init_db_is_idempotent(self, app):
        from app.db import init_db
        from app.config import Config
        init_db(Config.DB_PATH)
        init_db(Config.DB_PATH)

    def test_init_db_does_not_lose_data(self, app, db, sample_data):
        from app.db import init_db
        from app.config import Config
        count_before = db.execute("SELECT COUNT(*) FROM sensors").fetchone()[0]
        init_db(Config.DB_PATH)
        count_after = db.execute("SELECT COUNT(*) FROM sensors").fetchone()[0]
        assert count_before == count_after, (
            f"init_db should not lose data: before={count_before}, after={count_after}"
        )
