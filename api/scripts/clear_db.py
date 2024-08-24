#!/usr/local/bin/python

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

root_path = Path("../")
load_dotenv(dotenv_path=root_path / ".env")

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

db = psycopg2.connect(
    database=POSTGRES_DATABASE,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST,
    port=5432,
)
db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = db.cursor()

cursor.execute("DROP DATABASE gamersplane;")
cursor.execute("CREATE DATABASE gamersplane;")

cursor.execute("DROP DATABASE test_gamersplane;")
cursor.execute("CREATE DATABASE test_gamersplane;")

print("Dropped and recreated database\n")
