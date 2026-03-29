"""
core/parser.py — Read / write the Obsidian markdown file.
All file I/O is isolated here; nothing else touches the disk.
"""

from __future__ import annotations
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    Task, Session, TAG_PALETTES,
    colour_for_tag, fmt_dt, parse_dt,
    CLOCK_PATTERN, TASK_PATTERN, TAG_PATTERN,
)


class ParseResult:
    """Immutable snapshot of a parsed file."""

    def __init__(self, tasks: list[Task], raw_lines: list[str],
                 parsed_at: datetime):
        self.tasks      = tasks
        self.raw_lines  = raw_lines
        self.parsed_at  = parsed_at

    # Convenience look-ups
    def task_by_name(self, name: str) -> Optional[Task]:
        return next((t for t in self.tasks if t.name == name), None)


class VaultParser:
    """
    Parses an Obsidian markdown file that contains task entries with
    [clock::start--end] annotations.

    Thread-safe: parse() is stateless and returns a new ParseResult each call.
    """

    def parse(self, path: Path) -> ParseResult:
        if not path.exists():
            raise FileNotFoundError(f"Vault file not found: {path}")

        raw       = path.read_text(encoding="utf-8")
        lines     = raw.splitlines()
        tasks     = self._extract_tasks(lines)
        return ParseResult(tasks, lines, datetime.now())

    # ── Private ──────────────────────────────────────────────

    @staticmethod
    def _extract_tasks(lines: list[str]) -> list[Task]:
        tasks: list[Task]   = []
        tag_counters: dict[str, int] = {}
        current: Optional[Task]      = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            task_m = TASK_PATTERN.match(stripped)
            if task_m:
                if current is not None:
                    tasks.append(current)
                full_text = task_m.group(2)
                tag_m     = TAG_PATTERN.search(full_text)
                tag       = tag_m.group(1).lower() if tag_m else "none"
                name      = TAG_PATTERN.sub("", full_text).strip()
                name      = re.sub(r"\s+", " ", name).strip()

                idx = tag_counters.get(tag, 0)
                tag_counters[tag] = idx + 1

                current = Task(
                    name       = name,
                    tag        = tag,
                    colour     = colour_for_tag(tag, idx),
                    start_line = i,
                )
                continue

            if (current is not None
                    and line.startswith(" ")
                    and stripped.startswith("[clock::")):
                cm = CLOCK_PATTERN.match(stripped)
                if cm:
                    start_str = cm.group(1)
                    end_str   = cm.group(2)
                    start     = parse_dt(start_str)
                    end       = parse_dt(end_str) if end_str else None
                    if end is None or end > start:
                        current.sessions.append(
                            Session(start=start, end=end, line_index=i)
                        )
                continue

            # Non-indented non-empty line breaks the current task block
            if current is not None and stripped and not line.startswith(" "):
                tasks.append(current)
                current = None

        if current is not None:
            tasks.append(current)

        return tasks


class VaultWriter:
    """
    Writes clock-in / clock-out mutations back to the markdown file.
    Uses a file lock so concurrent writes don't corrupt the file.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def clock_in(self, path: Path, task_name: str,
                 parse_result: ParseResult) -> None:
        with self._lock:
            task = parse_result.task_by_name(task_name)
            if task is None:
                raise ValueError(f"Task '{task_name}' not found")
            if task.is_clocked_in:
                raise RuntimeError(f"Task '{task_name}' is already clocked in")

            lines = list(parse_result.raw_lines)
            insert_after = task.start_line
            for s in task.sessions:
                insert_after = max(insert_after, s.line_index)

            now_str  = fmt_dt(datetime.now())
            new_line = f"      [clock::{now_str}--]"
            lines.insert(insert_after + 1, new_line)
            path.write_text("\n".join(lines), encoding="utf-8")

    def clock_out(self, path: Path, task_name: str,
                  parse_result: ParseResult) -> None:
        with self._lock:
            task = parse_result.task_by_name(task_name)
            if task is None:
                raise ValueError(f"Task '{task_name}' not found")
            open_s = task.open_session
            if open_s is None:
                raise RuntimeError(f"Task '{task_name}' is not clocked in")

            lines    = list(parse_result.raw_lines)
            now_str  = fmt_dt(datetime.now())
            old_line = lines[open_s.line_index]
            new_line = re.sub(
                r"\[clock::(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})--\]",
                f"[clock::{{}}--{now_str}]".format(r"\1"),
                old_line,
            )
            # Simpler replacement that avoids regex backreference confusion
            new_line = old_line.replace("--]", f"--{now_str}]")
            lines[open_s.line_index] = new_line
            path.write_text("\n".join(lines), encoding="utf-8")
