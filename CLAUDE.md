# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Running the app

```bash
python run.py
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in PostgreSQL credentials before first run.

There are no tests or linting configuration in this project.

---

## Architecture

PyQt5 desktop app backed by **PostgreSQL**. All time data lives in the database.

### Data flow

```
PostgreSQL DB
    → DBStore.load()            → ParseResult (immutable snapshot)
    → RangeStats(tasks, s, e)   → aggregated metrics for a date window
    → InsightEngine.compute()   → list[Insight]
    → chart/widget .refresh()   → repaints QPainter widgets
```

Writes go through `DBStore` methods (`clock_in`, `clock_out`, `save_goals`, etc.), which use a threading lock around the SQLAlchemy session.

### Layer separation

- **`core/`** — zero UI imports. Pure data: models, DB access, analytics.
- **`ui/`** — PyQt5 only. Imports from `core/` but never from `charts/`.
- **`charts/`** — QPainter-based chart widgets. Imports from `core/` and `ui/theme`. No matplotlib.

### Key classes

| Class | File | Role |
|---|---|---|
| `Task`, `Session`, `GoalSpec` | `core/models.py` | Core dataclasses; `Session.end = None` means currently clocked in; `Task.start_line` holds DB `tasks.id`; `Session.line_index` holds DB clock record id |
| `DBStore` | `core/db_store.py` | Thread-safe PostgreSQL reads and writes; replaces old VaultParser/VaultWriter |
| `ParseResult` | `core/parser.py` | Immutable snapshot returned by `DBStore.load()` |
| `RangeStats` | `core/analytics.py` | Pre-computes daily/weekday/hourly aggregates for a date window |
| `InsightEngine` | `core/analytics.py` | Produces `Insight` objects (streak, peak hour, goal pace, etc.) |
| `TaskSessionStats` | `core/analytics.py` | Single-task aggregations within a date range |
| `MainWindow` | `ui/main_window.py` | Orchestrates everything; holds `_result`, `_goals`, `_task_rows` |
| `ReloadWorker` | `ui/main_window.py` | Runs `DBStore.load()` off the main thread via `QThread` |
| `CategoryTabWidget` | `ui/tab_widgets.py` | Full chart view scoped to one category |
| `TaskTabWidget` | `ui/tab_widgets.py` | Full chart/session view scoped to one task |
| `CalendarWidget` | `ui/calendar_widget.py` | Calendar tab — contribution graph + monthly grid + session day panel |

### Timers in MainWindow

- **1 s tick** (`_tick_timer`) — updates elapsed time on the active `TaskRow`
- **80 ms debounce** (`_refresh_timer`) — batches chart redraws after slider events
- **30 s auto-reload** (`_auto_reload`) — re-queries the DB in the background

### Goals

Goals (`GoalSpec`: hours + optional deadline) are stored in the DB `goals` table via `DBStore.save_goals()` / `DBStore.load_goals()`. They are applied to `Task` objects after each reload via `_apply_goals_to_tasks()`.

### Theme

All colours, spacing constants, and weekday name arrays live in `ui/theme.py`. Supports dark/light toggle via `set_dark_mode()` / `set_light_mode()`. Charts import tokens directly; `_propagate_to_consumers()` pushes updated values to all consumer modules at toggle time. `analytics.py` late-imports `WEEKDAY_NAMES` from `ui/theme` to avoid a circular import.

---

## Database schema

```
tasks            — id, name, category (str tag), color (hex)
historic_clocks  — id, tasks_id (FK), total_sec, start_time, end_time
current_clocks   — id, task_id (FK), start_time    ← open session
categories       — id, name, colour_tag             ← key into TAG_PALETTES
goals            — (managed via DBStore.save_goals)
```

Migrations live in `database/alembic/versions/`. Run with `alembic upgrade head`.

DB connection is configured via `.env`:
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:port/dbname
```
or individual vars: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`.

---

## Charts inventory (`charts/panels.py`)

| Chart | Class | Used in |
|---|---|---|
| Stacked area (daily totals) | `StackedAreaChart` | Main tab, Category tab |
| Weekday bar (avg by weekday) | `WeekdayBarChart` | Main tab, Category tab |
| Hour heatmap | `HourHeatmap` | Main tab, Category tab |
| Week-over-week comparison | `WeeklyCompChart` | Main tab, Category tab |
| Category breakdown bar | `CategoryBreakdownChart` | Main tab |
| Category pie | `CategoryPieChart` | Category tab |
| Daily bar (single task) | `DailyBarChart` | Task tab |
| Session length histogram | `SessionHistogramChart` | Task tab |
| Time-of-day bar | `TimeOfDayBarChart` | Task tab |
| Cumulative pace | `CumulativePaceChart` | Task tab |

All charts receive data via a `.refresh(data)` call and repaint via `QPainter`.

---

## Calendar tab (`ui/calendar_widget.py`)

Implemented. File: `time_tracker/ui/calendar_widget.py`.  Added as a pinned tab (index 1, non-closeable) in `MainWindow`.

### Classes

| Class | Role |
|---|---|
| `ContributionGraph` | GitHub-style 52-week heat map (QPainter). Colours assigned by **percentile rank** of each day vs all days (top 10 % → brightest). Hover tooltip shows date + hours. Click to jump to that week. |
| `WeekGridWidget` | 7-column week timeline (QPainter). Sessions positioned by clock time — y-axis is 24 h, height is proportional to duration. Hover a block → inline edit (click body) / delete (click ✕ corner). Click empty space → add dialog pre-filled to that time slot. 60-second timer refreshes the current-time indicator. |
| `CalendarWidget` | Top-level assembly. Contribution strip (no title) + week nav bar + scrollable `WeekGridWidget`. `reload_needed` signal propagates to `MainWindow._trigger_reload`. |
| `_CalendarAddSessionDialog` | Modal — task picker + start/end datetime pickers. Accepts `preset_start`/`preset_end` so the click position pre-fills the time. |

### Data flow

```
ParseResult.tasks  →  CalendarWidget.refresh()
    → ContributionGraph.refresh(total_by_day)      # seconds summed per day
    → MonthGridWidget.refresh(tasks)               # sessions grouped by date
    → SessionDayPanel.show_day(date, tasks)        # on day click
```

Writes go directly through `DBStore.update_session`, `DBStore.delete_session`, `DBStore.add_session`, then `reload_needed` is emitted to trigger a full reload.
