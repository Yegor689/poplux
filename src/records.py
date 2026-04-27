"""Persistent records storage using the platform-appropriate data directory."""
from __future__ import annotations
import json
import os
from datetime import date

import platformdirs

_DATA_DIR = platformdirs.user_data_dir("Poplux")
_RECORDS_FILE = os.path.join(_DATA_DIR, "records.json")

_cache: list[dict] | None = None


def load() -> list[dict]:
    """Return all saved records, newest first. Returns [] on missing/corrupt file.
    Result is cached in memory; invalidated by save()."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(_RECORDS_FILE, encoding="utf-8") as f:
            _cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cache = []
    return _cache


def save(level_name: str, score: int, elapsed: float) -> None:
    """Append a new record and persist to disk."""
    global _cache
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
    _cache = None  # invalidate so next load() re-reads from disk


def top(n: int = 50) -> list[dict]:
    """Return up to n normal-level records sorted by score descending."""
    all_r = [r for r in load() if not r["level"].startswith("Endless")]
    return sorted(all_r, key=lambda r: r["score"], reverse=True)[:n]


def top_endless(n: int = 50) -> list[dict]:
    """Return up to n endless-mode records sorted by score descending."""
    all_r = [r for r in load() if r["level"].startswith("Endless")]
    return sorted(all_r, key=lambda r: r["score"], reverse=True)[:n]


def best_by_level() -> dict[str, dict]:
    """Return the best (highest-score) normal-level record for each level name."""
    result: dict[str, dict] = {}
    for r in load():
        name = r["level"]
        if name.startswith("Endless"):
            continue
        if name not in result or r["score"] > result[name]["score"]:
            result[name] = r
    return result


def best_by_endless() -> dict[str, dict]:
    """Return the best (highest-score) endless record per level slot."""
    result: dict[str, dict] = {}
    for r in load():
        name = r["level"]
        if not name.startswith("Endless"):
            continue
        if name not in result or r["score"] > result[name]["score"]:
            result[name] = r
    return result


def is_new_best(level_name: str, score: int) -> bool:
    """Return True if score is strictly better than the previous best for this level."""
    best = best_by_level().get(level_name)
    return best is None or score > best["score"]


def max_unlocked(levels: list) -> int:
    """Return the highest level index (0-based) the player has access to.
    Level 0 is always unlocked.  Completing level N unlocks level N+1."""
    completed = {r["level"] for r in load()}
    unlocked = 0
    for i, cfg in enumerate(levels):
        if cfg["name"] in completed:
            unlocked = min(i + 1, len(levels) - 1)
    return unlocked
