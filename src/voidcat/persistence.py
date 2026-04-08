from __future__ import annotations

import json
import os
from pathlib import Path

from .models import MAX_HIGH_SCORES, ScoreEntry


def score_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".local" / "share"
    return root / "voidcat" / "scores.json"


def load_scores(path: Path | None = None) -> list[ScoreEntry]:
    destination = path or score_path()
    try:
        raw = json.loads(destination.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    scores: list[ScoreEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            scores.append(ScoreEntry.from_dict(item))
        except (KeyError, TypeError, ValueError):
            continue
    scores.sort(key=lambda entry: entry.score, reverse=True)
    return scores[:MAX_HIGH_SCORES]


def save_scores(entries: list[ScoreEntry], path: Path | None = None) -> tuple[bool, str | None]:
    destination = path or score_path()
    ordered = sorted(entries, key=lambda entry: entry.score, reverse=True)[:MAX_HIGH_SCORES]
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([entry.to_dict() for entry in ordered], indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        return False, str(exc)
    return True, None
