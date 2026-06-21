from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from .config import Settings


async def migrate() -> None:
    settings = Settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        for path in sorted(Path("migrations").glob("*.sql")):
            await conn.execute(path.read_text())
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
