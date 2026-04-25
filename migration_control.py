from __future__ import annotations

import hashlib
import re
from pathlib import Path

from db import connect_to_db

MIGRATION_FILE_RE = re.compile(r"^(\d+)__([a-zA-Z0-9_\-]+)\.sql$")


def _migration_checksum(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def _ensure_migrations_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _get_applied_migrations(cursor) -> dict[int, tuple[str, str]]:
    cursor.execute("SELECT version, name, checksum FROM schema_migrations")
    rows = cursor.fetchall()
    return {row[0]: (row[1], row[2]) for row in rows}


def _read_migrations(migrations_dir: Path) -> list[tuple[int, str, str]]:
    if not migrations_dir.exists():
        return []

    migrations: list[tuple[int, str, str]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = MIGRATION_FILE_RE.match(path.name)
        if not match:
            continue
        version = int(match.group(1))
        name = match.group(2)
        sql_text = path.read_text(encoding="utf-8").strip()
        if not sql_text:
            continue
        migrations.append((version, name, sql_text))
    return migrations


def apply_migrations(migrations_dir: str | Path = "migrations") -> list[int]:
    migrations_path = Path(migrations_dir)
    migrations = _read_migrations(migrations_path)
    if not migrations:
        return []

    applied_now: list[int] = []
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            _ensure_migrations_table(cursor)
            applied = _get_applied_migrations(cursor)

            for version, name, sql_text in migrations:
                checksum = _migration_checksum(sql_text)
                existing = applied.get(version)
                if existing:
                    existing_name, existing_checksum = existing
                    if existing_name != name or existing_checksum != checksum:
                        raise RuntimeError(
                            f"Migration {version} is already applied with different content."
                        )
                    continue

                cursor.execute(sql_text)
                cursor.execute(
                    """
                    INSERT INTO schema_migrations (version, name, checksum)
                    VALUES (%s, %s, %s)
                    """,
                    (version, name, checksum),
                )
                applied_now.append(version)

    return applied_now
