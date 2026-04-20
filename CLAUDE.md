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

No configuration needed. A SQLite database is created automatically at `timetracker.db` in the project root on first launch.

There are no tests or linting configuration in this project.

## App icon

`time_tracker/icon.png` (512×512). Loaded at startup in `run.py` via `QApplication.setWindowIcon` and in `MainWindow.__init__` via `self.setWindowIcon`. Both use `Path(__file__)` resolution so the path is portable.

## Fonts

Geist and Geist Mono TTF files live in `time_tracker/fonts/`. They are loaded via `QFontDatabase.addApplicationFont` in `run.py` before `MainWindow` is created. Fallback stacks: `'Geist, Segoe UI, sans-serif'` and `'Geist Mono, Consolas, monospace'`.

---

## Architecture

PyQt5 desktop app backed by **SQLite**. All time data lives in a local `timetracker.db` file.

### Data flow

```
SQLite DB
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
| `DBStore` | `core/db_store.py` | Thread-safe SQLite reads and writes via SQLAlchemy; `set_archived` toggles task visibility |
| `ParseResult` | `core/parser.py` | Immutable snapshot returned by `DBStore.load()` |
| `RangeStats` | `core/analytics.py` | Pre-computes daily/weekday/hourly aggregates for a date window |
| `InsightEngine` | `core/analytics.py` | Produces `Insight` objects (streak, peak hour, goal pace, etc.) |
| `TaskSessionStats` | `core/analytics.py` | Single-task aggregations within a date range |
| `MainWindow` | `ui/main_window.py` | Orchestrates everything; holds `_result`, `_goals`; sidebar-driven navigation via `QStackedWidget`; `_show_archived` toggle filters archived tasks |
| `ReloadWorker` | `ui/main_window.py` | Runs `DBStore.load()` off the main thread via `QThread` |
| `UpdateChecker` | `ui/main_window.py` | Checks GitHub releases API on startup; emits `update_available` signal if a newer version exists |
| `CategoryTabWidget` | `ui/tab_widgets.py` | Full chart view scoped to one category |
| `TaskTabWidget` | `ui/tab_widgets.py` | Full chart/session view scoped to one task |
| `GoalsTab` | `ui/goals_tab.py` | Goals view — KPI header bar + scrollable grid of `_GoalCard` widgets |
| `CalendarWidget` | `ui/calendar_widget.py` | Calendar view — contribution graph + week navigation + `WeekGridWidget` |
| `BaseFormDialog` | `ui/dialogs/base.py` | Shared base class for all modal dialogs; applies `SS.dialog()` stylesheet |
| `SS` | `ui/theme.py` | Stylesheet factory — `SS.button(variant)`, `SS.input()`, `SS.combo()`, `SS.scrollarea()`, `SS.dialog()` |

### Navigation

`MainWindow` uses a `QStackedWidget` (not `QTabWidget`) for the right panel. The left sidebar drives navigation:

- **Nav section** — Overview / Calendar / Goals items; clicking calls `_select_view("overview"|"calendar"|"goals")`
- **Category headers** — clicking opens a `CategoryTabWidget` on demand (`_select_view("cat:name")`); the arrow button collapses/expands the task list
- **Task items** — clicking opens a `TaskTabWidget` on demand (`_select_view("task:name")`)
- `_category_views` and `_task_views` dicts cache created views so they aren't rebuilt on every visit

### Timers in MainWindow

- **1 s tick** (`_tick_timer`) — updates elapsed time in the session bar when clocked in
- **80 ms debounce** (`_refresh_timer`) — batches chart redraws after date slider events
- **30 s auto-reload** (`_auto_reload`) — re-queries the DB in the background

### Goals

Goals (`GoalSpec`: hours + optional deadline) are stored in the DB `goals` table via `DBStore.save_goals()` / `DBStore.load_goals()`. Applied to `Task` objects after each reload via `_apply_goals_to_tasks()`. Goals auto-archive 3 days after `completed_on` is set.

### Theme

All colours, spacing constants, and font stacks live in `ui/theme.py`. Supports dark/light toggle via `set_dark_mode()` / `set_light_mode()`. `_propagate_to_consumers()` pushes updated values to all consumer modules at toggle time. The `SS` class provides stylesheet factory methods used throughout the UI. `analytics.py` late-imports `WEEKDAY_NAMES` from `ui/theme` to avoid a circular import.

Key tokens: `BG`, `BG2`, `BG3`, `BG4`, `BORDER`, `BORDER2`, `TEXT`, `DIM`, `MUTED`, `FAINT`, `ACCENT`, `SUCCESS`, `WARNING`, `DANGER`, `FONT_UI`, `FONT_MONO`, `RADIUS`, `RADIUS_LG`, `PAD`, `PAD_MD`, `PAD_LG`, `CHART_COLORS`.

---

## Database schema

```
tasks            — id, name, category (str tag), color (hex), archived (bool)
historic_clocks  — id, tasks_id (FK), total_sec, start_time, end_time
current_clocks   — id, task_id (FK), start_time    ← open session
categories       — id, name, colour_tag             ← key into TAG_PALETTES
goals            — id, tasks_id (FK), target_hours, by_date, completed_on, archived
```

Migrations live in `database/alembic/versions/`. They run automatically on startup via `database/migrate.py` — no manual `alembic` commands needed.

DB path: `timetracker.db` in project root (dev) or `%LOCALAPPDATA%/TimeTracker/timetracker.db` (frozen exe).

---

## Charts inventory (`charts/panels.py`)

| Chart | Class | Used in |
|---|---|---|
| Stacked area (daily totals) | `StackedAreaChart` | Overview, Category view |
| Weekday bar (avg by weekday) | `WeekdayBarChart` | Overview, Category view |
| Hour heatmap | `HourHeatmap` | Overview, Category view |
| Week-over-week comparison | `WeeklyCompChart` | Overview, Category view |
| Category pie | `CategoryPieChart` | Overview, Category view |
| Daily bar (single task) | `DailyBarChart` | Task view |
| Session length histogram | `SessionHistogramChart` | Task view |
| Time-of-day bar | `TimeOfDayBarChart` | Task view |
| Cumulative pace | `CumulativePaceChart` | Task view |

All charts receive data via a `.refresh(data)` call and repaint via `QPainter`. Grid lines use `Qt.DashLine`. Colors come from `CHART_COLORS` in `theme.py`.

---

## Calendar view (`ui/calendar_widget.py`)

| Class | Role |
|---|---|
| `ContributionGraph` | GitHub-style 52-week heat map (QPainter). Colours by percentile rank. Hover tooltip shows date + hours. Click jumps to that week. |
| `WeekGridWidget` | 7-column week timeline (QGraphicsView). Sessions positioned by clock time; height proportional to duration. Click session to edit/delete; click empty space to add. |
| `CalendarWidget` | Assembly: contribution strip + week nav bar + `WeekGridWidget`. Emits `reload_needed` after any write. |
| `_CalendarAddSessionDialog` | Task picker + datetime pickers. Pre-fills time from click position. |

---

## Dialogs (`ui/dialogs/`)

All dialogs extend `BaseFormDialog` from `ui/dialogs/base.py`, which applies `SS.dialog()` styling and provides `_make_field()`, `_make_header()`, and `_make_footer()` helpers.

| File | Dialogs |
|---|---|
| `goal_dialogs.py` | `AddGoalDialog`, `EditGoalDialog` |
| `task_dialogs.py` | `NewTaskDialog`, `RenameTaskDialog`, `MoveTaskDialog` |
| `category_dialogs.py` | `NewCategoryDialog`, `RenameCategoryDialog` |
| `session_dialogs.py` | `AddSessionDialog`, `EditSessionDialog` |
