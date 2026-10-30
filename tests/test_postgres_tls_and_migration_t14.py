"""
tests/test_postgres_tls_and_migration_t14.py

Acceptance tests for T14:
Repair TLS, schema creation, and migration ownership.
"""

import ssl
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.database.postgres import (
    MigrationError,
    _build_ssl_context,
    init_tiger_schema,
    parse_sql_script,
)


def test_tls_context_enforces_cert_and_hostname_verification(monkeypatch):
    """SSL context for hosted Postgres verifies hostname and certificates by default."""
    monkeypatch.delenv("POSTGRES_INSECURE_DISABLE_TLS_VERIFY", raising=False)

    ctx = _build_ssl_context("postgresql://user:pass@db.supabase.co:5432/postgres?sslmode=require")
    assert ctx is not None
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED

    # Disabling requires explicit environment variable override
    monkeypatch.setenv("POSTGRES_INSECURE_DISABLE_TLS_VERIFY", "true")
    insecure_ctx = _build_ssl_context("postgresql://user:pass@db.supabase.co:5432/postgres?sslmode=require")
    assert insecure_ctx.check_hostname is False
    assert insecure_ctx.verify_mode == ssl.CERT_NONE


def test_parse_sql_script_preserves_commented_statements():
    """SQL statements preceded by comments are not discarded."""
    sql = """
    -- =============================================================================
    -- Header comment
    -- =============================================================================
    CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

    /* Multi-line block comment
       about code_chunks table */
    CREATE TABLE IF NOT EXISTS code_chunks (
        id UUID PRIMARY KEY,
        repo TEXT NOT NULL -- inline comment
    );
    """
    statements = parse_sql_script(sql)
    assert len(statements) == 2
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE" in statements[0]
    assert "CREATE TABLE IF NOT EXISTS code_chunks" in statements[1]
    assert not statements[0].startswith("--")
    assert not statements[1].startswith("/*")


@pytest.mark.asyncio
async def test_init_tiger_schema_raises_on_required_ddl_failure(monkeypatch):
    """init_tiger_schema must raise MigrationError if table creation DDL fails."""
    monkeypatch.setattr("backend.database.postgres._asyncpg.create_pool", AsyncMock())

    with patch("backend.database.postgres.get_settings") as mock_settings, \
         patch("backend.database.postgres._asyncpg.create_pool") as mock_pool_creator:

        settings_obj = MagicMock()
        settings_obj.tiger_database_url = "postgresql://user:pass@localhost:5432/pr_review"
        settings_obj.database_url = "postgresql://user:pass@localhost:5432/pr_review"
        mock_settings.return_value = settings_obj

        mock_conn = AsyncMock()

        async def fake_execute(stmt):
            if "CREATE TABLE" in stmt.upper():
                raise RuntimeError("Syntax error in table creation")
            return "OK"

        mock_conn.execute.side_effect = fake_execute

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool_creator.return_value = mock_pool

        with pytest.raises(MigrationError):
            await init_tiger_schema()
