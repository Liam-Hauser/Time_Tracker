"""core/user_presets.py — Persistent custom date-range presets."""
from __future__ import annotations
import json
import sys
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

MAX_CUSTOM_PRESETS = 5


@dataclass
class CustomPreset:
    label:     str
    from_date: date
    to_date:   Optional[date]   # None = always use today (rolling)


def _presets_path() -> Path:
    if getattr(sys, "frozen", False):
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "TimeTracker" / "custom_presets.json"
    return Path(__file__).parent.parent.parent / "custom_presets.json"


def load_presets() -> list[CustomPreset]:
    p = _presets_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        result = []
        for item in data:
            from_d = date.fromisoformat(item["from"])
            to_d   = date.fromisoformat(item["to"]) if item.get("to") else None
            result.append(CustomPreset(label=item["label"], from_date=from_d, to_date=to_d))
        return result
    except Exception:
        return []


def save_presets(presets: list[CustomPreset]) -> None:
    p = _presets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "label": pr.label,
            "from":  pr.from_date.isoformat(),
            "to":    pr.to_date.isoformat() if pr.to_date else None,
        }
        for pr in presets
    ]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
