#!/usr/local/bin/python

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

root_path = Path("../")
load_dotenv(dotenv_path=root_path / ".env")

DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_DATABASE = os.getenv("DATABASE_DATABASE")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")


async def main():
    conn = await asyncpg.connect(
        host=DATABASE_HOST,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
    )

    await conn.execute(f"DROP OWNED BY {DATABASE_USER}")
    # await conn.execute("DROP DATABASE gamersplane;")
    # await conn.execute("CREATE DATABASE gamersplane;")

    # await conn.execute("DROP DATABASE test_gamersplane;")
    # await conn.execute("CREATE DATABASE test_gamersplane;")

    print("Dropped and recreated database\n")

    await conn.close()


asyncio.run(main())
