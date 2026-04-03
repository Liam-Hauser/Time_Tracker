# Time Tracker

A PyQt5 desktop application for detailed time tracking and analytics. Data is stored locally in SQLite — no database setup required.

## Features

- **Task management** — Tasks organised by category with colour tags; rename, move, delete from the UI
- **Clock in/out** — Start and stop timing sessions from the task list
- **Live elapsed time** — Active session timer updates every second
- **Goal tracking** — Set target hours and deadlines per task with pace calculations
- **Tabbed analytics** — Overview, per-category, and per-task dashboards
- **Charts** — Daily breakdown, weekday averages, weekly comparison, hourly heatmap, session histograms, cumulative pace
- **Insight engine** — Auto-generated insights: peak hours, best day, week-over-week delta, streak
- **Calendar tab** — GitHub-style 52-week contribution heat map + 7-column week timeline; click to add, edit, or delete sessions
- **Session management** — Manually add, edit, or delete sessions from the task tab or calendar
- **Dark / light theme** — Toggle in the top bar
- **Auto-reload** — DB reloads in the background every 30 seconds
- **Update notifications** — Checks GitHub releases on startup and shows a button when a newer version is available

## Distribution

Download the latest `TimeTracker.exe` from [Releases](https://github.com/Liam-Hauser/Time_Tracker/releases/latest). No install, no Python required.

Data is stored at `%LOCALAPPDATA%\TimeTracker\timetracker.db`. Replacing the exe with a newer version preserves all existing data.

## Development setup

```bash
pip install -r requirements.txt
python run.py
```

No `.env` or database configuration needed. A SQLite database is created automatically at `timetracker.db` in the project root on first launch.

## Building the exe

```bash
python build.py
```

Output: `dist/TimeTracker.zip` (contains `TimeTracker.exe`) — ready to upload to a GitHub release.

## Project Structure

```
time_tracker/
├── version.py          # VERSION constant and GITHUB_REPO
├── icon.png            # Application icon (512×512)
├── core/
│   ├── models.py       # Task, Session, GoalSpec dataclasses + TAG_PALETTES
│   ├── db_store.py     # DBStore — thread-safe SQLite reads and writes
│   ├── parser.py       # ParseResult container (returned by DBStore.load)
│   └── analytics.py    # RangeStats, GoalTracker, InsightEngine, TaskSessionStats
├── ui/
│   ├── main_window.py      # Top-level QMainWindow; orchestrates tabs and timers
│   ├── tab_widgets.py      # CategoryTabWidget, TaskTabWidget
│   ├── calendar_widget.py  # CalendarWidget — contribution graph + week timeline
│   ├── widgets.py          # Reusable components (MetricCard, TaskRow, GoalRow, …)
│   └── theme.py            # Dark/light colour tokens and spacing constants
├── charts/
│   └── panels.py       # QPainter chart panels (area, bar, heatmap, pie, etc.)
database/
├── db.py               # SQLAlchemy engine + SessionLocal (SQLite)
├── migrate.py          # Runs Alembic on startup; stamps existing DBs automatically
├── models/             # ORM models: Task, HistoricClock, CurrentClock, Category, Goal
└── alembic/            # Migration scripts
run.py                  # Entry point
TimeTracker.spec        # PyInstaller build spec
requirements.txt
```

## Database Schema

| Table | Key columns |
|---|---|
| `tasks` | `id`, `name`, `category`, `color` |
| `historic_clocks` | `id`, `tasks_id`, `start_time`, `end_time`, `total_sec` |
| `current_clocks` | `id`, `task_id`, `start_time` — one row = active session |
| `categories` | `id`, `name`, `colour_tag` |
| `goals` | `id`, `tasks_id`, `name`, `target_hours`, `by_date` |
