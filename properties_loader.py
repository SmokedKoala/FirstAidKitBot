"""Load KEY=value pairs from private.properties into os.environ (setdefault: real env wins)."""

from __future__ import annotations

import os
from pathlib import Path


def load_private_properties(path: str | Path | None = None) -> Path | None:
    """
    Read properties file (UTF-8). Lines: KEY=value, empty lines and # comments ignored.
    Does not override variables already set in the environment.
    Returns path used if file existed, else None.
    """
    base = Path(__file__).resolve().parent
    prop_path = Path(path) if path is not None else base / "private.properties"
    if not prop_path.is_file():
        return None

    with prop_path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, val = line.partition("=")
            if not sep:
                continue
            key, val = key.strip(), val.strip()
            if not key:
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            os.environ.setdefault(key, val)

    return prop_path
