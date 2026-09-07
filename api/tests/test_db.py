import pytest

from app.db import migrate

pytestmark = pytest.mark.anyio


async def test_migrate_applies_each_file_once(db_conn):
    first = await migrate(db_conn)
    second = await migrate(db_conn)

    assert first == ["001_initial.sql", "002_embeddings.sql", "003_traces.sql", "004_extraction.sql"]
    assert second == []
    cur = await db_conn.execute("SELECT name FROM schema_migrations ORDER BY name")
    assert [row[0] for row in await cur.fetchall()] == first
