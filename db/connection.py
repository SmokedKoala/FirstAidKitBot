import os

import psycopg2


def connect_to_db():
    """
    Connect to PostgreSQL using DATABASE_URL if provided, otherwise
    fall back to PG* env vars suitable for local/Docker setups.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        database=os.environ.get("PGDATABASE", "firstaidkitbot"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
    )

