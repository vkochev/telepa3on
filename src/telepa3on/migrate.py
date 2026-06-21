from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg

from .config import Settings


def migrations_dir() -> Path:
    if configured := os.getenv("MIGRATIONS_DIR"):
        return Path(configured)
    candidates = [Path.cwd() / "migrations", Path(__file__).resolve().parents[2] / "migrations"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


async def migrate() -> None:
    settings = Settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        async with conn.transaction():
            for path in sorted(migrations_dir().glob("*.sql")):
                already_applied = await conn.fetchval("SELECT 1 FROM schema_migrations WHERE version = $1", path.name)
                if already_applied:
                    continue
                await conn.execute(path.read_text())
                await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.name)
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
