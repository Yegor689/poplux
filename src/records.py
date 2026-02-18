"""Persistent records storage using the platform-appropriate data directory."""
from __future__ import annotations
import json
import os
from datetime import date

import platformdirs

_DATA_DIR = platformdirs.user_data_dir("Poplux")
_RECORDS_FILE = os.path.join(_DATA_DIR, "records.json")


def load() -> list[dict]:
    """Return all saved records, newest first. Returns [] on missing/corrupt file."""
    try:
        with open(_RECORDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(level_name: str, score: int, elapsed: float) -> None:
    """Append a new record and persist to disk."""
    records = load()
    records.append({
        "level": level_name,
        "score": score,
        "time": round(elapsed, 1),
        "date": date.today().isoformat(),
    })
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def top(n: int = 50) -> list[dict]:
    """Return up to n records sorted by score descending."""
    return sorted(load(), key=lambda r: r["score"], reverse=True)[:n]
