# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
python run.py
# or with a specific vault file:
python run.py /path/to/vault/2026-Q1.md
```

Install dependencies:
```bash
pip install -r requirements.txt
```

There are no tests or linting configuration in this project.

## Architecture

This is a PyQt5 desktop app that reads/writes time-tracking data stored as `[clock::START--END]` inline annotations in an Obsidian-compatible markdown file.

### Data flow

```
Vault .md file
    → VaultParser.parse()       → ParseResult (immutable snapshot)
    → RangeStats(tasks, s, e)   → aggregated metrics for a date range
    → InsightEngine.compute()   → list[Insight]
    → chart/widget .refresh()   → repaints QPainter widgets
```

Writes go through `VaultWriter` (clock_in / clock_out), which uses a threading lock and writes back to the file in-place by mutating `raw_lines`.

### Layer separation

- **`core/`** — zero UI imports. Pure data: models, parsing, analytics.
- **`ui/`** — PyQt5 only. Imports from `core/` but never from `charts/`.
- **`charts/`** — QPainter-based chart widgets. Imports from `core/` and `ui/theme`. All charts render natively (no matplotlib).

### Key classes

| Class | File | Role |
|---|---|---|
| `Task`, `Session`, `GoalSpec` | `core/models.py` | Core dataclasses; `Session.end = None` means currently clocked in |
| `VaultParser` | `core/parser.py` | Stateless; returns `ParseResult` each call |
| `VaultWriter` | `core/parser.py` | Thread-safe file mutations |
| `RangeStats` | `core/analytics.py` | Pre-computes daily/weekday/hourly aggregates for a date window |
| `InsightEngine` | `core/analytics.py` | Produces `Insight` objects (streak, peak hour, goal pace, etc.) |
| `MainWindow` | `ui/main_window.py` | Orchestrates everything; holds `_result`, `_goals`, `_task_rows` |
| `ReloadWorker` | `ui/main_window.py` | Runs `VaultParser.parse()` off the main thread via `QThread` |

### Timers in MainWindow

- **1 s tick** (`_tick_timer`) — updates elapsed time on the active `TaskRow`
- **80 ms debounce** (`_refresh_timer`) — batches chart redraws after slider events
- **30 s auto-reload** (`_auto_reload`) — re-parses the vault file in the background

### Goals

Goals (`GoalSpec`: hours + optional deadline) are stored on `MainWindow._goals` (a `dict[str, GoalSpec]`), not in the vault file. They are applied to `Task` objects after each reload via `_apply_goals_to_tasks()`.

### Theme

All colours, spacing constants, and weekday name arrays live in `ui/theme.py`. Charts import from there directly. `analytics.py` has one late import of `WEEKDAY_NAMES` from `ui/theme` (to avoid a circular import).

### Data format

```markdown
- [ ] Task name #blue [clock::2026-03-30T09:00:00--2026-03-30T10:30:00]
      [clock::2026-03-30T11:00:00--]   ← open session (clocked in)
```

Clock entries must be indented (starts with a space). A non-indented, non-empty line terminates the current task block in the parser.
