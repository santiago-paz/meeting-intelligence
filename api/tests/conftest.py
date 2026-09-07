"""Shared fixtures.

Storage tests run against a real Postgres, the one from docker-compose.yml.
They read DATABASE_URL (from the environment or api/.env) and use a sibling
database named <dbname>_test, recreated from an empty schema for every test,
so development data is never touched. Without DATABASE_URL they are skipped.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo

load_dotenv()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("set DATABASE_URL (docker compose up -d db) to run storage tests")
    params = conninfo_to_dict(url)
    test_name = f"{params['dbname']}_test"
    admin_url = make_conninfo(**{**params, "dbname": "postgres"})
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{test_name}"')
    return make_conninfo(**{**params, "dbname": test_name})


@pytest.fixture
async def db_conn(test_db_url: str):
    """An autocommit connection to an empty public schema."""
    async with await psycopg.AsyncConnection.connect(test_db_url, autocommit=True) as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        yield conn


@pytest.fixture
async def migrated_conn(db_conn):
    """db_conn with the current schema applied."""
    from app.db import migrate

    await migrate(db_conn)
    return db_conn


def _client(test_db_url: str, monkeypatch, *, with_llm: bool):
    """A TestClient whose lifespan ran against an empty test database.

    Model-backed services are replaced by fakes so the suite stays offline and
    fast; the key is blanked so no real client is ever built here.
    """
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    from fastapi.testclient import TestClient

    from app.main import app, get_embedder, get_enricher
    from tests.fakes import FakeEmbedder, FakeEnricher

    app.dependency_overrides[get_embedder] = FakeEmbedder
    if with_llm:
        app.dependency_overrides[get_enricher] = FakeEnricher
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(test_db_url: str, monkeypatch):
    yield from _client(test_db_url, monkeypatch, with_llm=True)


@pytest.fixture
def client_without_llm(test_db_url: str, monkeypatch):
    """The app as it boots with no ANTHROPIC_API_KEY configured."""
    yield from _client(test_db_url, monkeypatch, with_llm=False)
