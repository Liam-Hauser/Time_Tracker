# Time Tracker

A PyQt5 desktop application for detailed time tracking and analytics. Data is stored in PostgreSQL, managed via SQLAlchemy and Alembic.

## Features

- **Task management** — Tasks organised by category with colour tags
- **Clock in/out** — Start and stop timing sessions from the UI
- **Live elapsed time** — Active session timer updates every second
- **Goal tracking** — Set target hours and deadlines per task with pace calculations
- **Tabbed analytics** — Overview, per-category, and per-task dashboards
- **Charts** — Daily breakdown, weekday averages, weekly comparison, hourly heatmap, session histograms, cumulative pace
- **Insight engine** — Auto-generated insights (peak hours, best day, week-over-week delta)
- **Calendar tab** — GitHub-style contribution heat map + Google Calendar-style monthly grid; click any day to view, edit, delete, or add sessions
- **Dark / light theme** — Toggle in the top bar
- **Auto-reload** — DB reloads in the background every 30 seconds

## Requirements

- Python 3.9+
- PostgreSQL (local or remote)
- PyQt5, numpy, SQLAlchemy, psycopg2-binary, Alembic, python-dotenv

```bash
pip install -r requirements.txt
```

## Setup

1. Copy `.env.example` to `.env` and fill in your PostgreSQL credentials:

```env
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/time_tracker
```

2. Run migrations:

```bash
alembic upgrade head
```

3. Launch:

```bash
python run.py
```

## Project Structure

```
time_tracker/
├── core/
│   ├── models.py       # Task, Session, GoalSpec dataclasses + TAG_PALETTES
│   ├── db_store.py     # DBStore — thread-safe PostgreSQL reads and writes
│   ├── parser.py       # ParseResult container (returned by DBStore.load)
│   └── analytics.py    # RangeStats, GoalTracker, InsightEngine, TaskSessionStats
├── ui/
│   ├── main_window.py  # Top-level QMainWindow; orchestrates tabs and timers
│   ├── tab_widgets.py      # CategoryTabWidget, TaskTabWidget
│   ├── calendar_widget.py  # CalendarWidget — contribution graph + month grid
│   ├── widgets.py      # Reusable components (MetricCard, TaskRow, SessionTable, …)
│   └── theme.py        # Dark/light colour tokens and spacing constants
├── charts/
│   └── panels.py       # QPainter chart panels (area, bar, heatmap, pie, etc.)
database/
├── db.py               # SQLAlchemy engine + SessionLocal
├── models/             # ORM models: Task, HistoricClock, CurrentClock, Category
└── alembic/            # Migration scripts
run.py                  # Entry point
.env.example            # Environment variable template
requirements.txt
```

## Database Schema

| Table | Key columns                                              |
|---|----------------------------------------------------------|
| `tasks` | `id`, `name`, `category`, `color`                        |
| `historic_clocks` | `id`, `tasks_id`, `start_time`, `end_time`, `total_sec`  |
| `current_clocks` | `id`, `task_id`, `start_time` — one row = active session |
| `categories` | `id`, `name`, `colour_tag`                               |
| `goals` | `id`, `task_id`, `name`, `target_hours`, `by_date`        |
