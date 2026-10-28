"""Exit 0 if the database from DATABASE_URL accepts connections, else 1."""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def main() -> int:
    url = make_url(settings.database_url)
    engine = create_async_engine(url, connect_args={"timeout": 3})
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any failure means unreachable
        print(
            f"Cannot reach PostgreSQL at {url.host}:{url.port} "
            f"(database {url.database}): {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
