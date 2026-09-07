"""Database access: the migration runner. The pool lives in the app lifespan."""

from pathlib import Path

from psycopg import AsyncConnection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def migrate(conn: AsyncConnection) -> list[str]:
    """Apply every migration file not yet recorded, in filename order.

    Returns the names applied in this run. The whole run is one transaction,
    so a failing file leaves nothing behind, not even the bookkeeping row.
    """
    applied_now: list[str] = []
    async with conn.transaction():
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name text PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        cur = await conn.execute("SELECT name FROM schema_migrations")
        already = {row[0] for row in await cur.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in already:
                continue
            await conn.execute(path.read_text())
            await conn.execute(
                "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
            )
            applied_now.append(path.name)
    return applied_now
