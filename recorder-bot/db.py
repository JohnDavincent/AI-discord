from __future__ import annotations
import os
import asyncpg
from datetime import datetime,timezone

_pool: asyncpg.Pool | None = None

def _dsn() -> str:
    return (
        f"postgresql://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}"
        f"@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
    )

async def connect() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=5)
    return _pool

async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("db.connect() belum dipanggil karena pool masih None")

    return _pool


if __name__ == "__main__" :
    import asyncio
    from dotenv import load_dotenv

    async def _main():
        load_dotenv()
        pool = await connect()
        print(await pool.fetchval("SELECT 1"))
        await close()

    asyncio.run(_main())
