# Time Tracker

A PyQt5 desktop application for detailed time tracking and analytics. Data is stored locally in SQLite — no database setup required.

## Features

- **Task management** — Tasks organised by category; rename, move, archive, or delete from the UI
- **Clock in/out** — Start and stop timing sessions from the sidebar; elapsed timer shown at the top of the left panel
- **Goal tracking** — Set target hours and optional deadlines per task; pace calculations, on-track/behind status, auto-archive on completion
- **Analytics dashboards** — Overview, per-category, and per-task views with mean and standard deviation stats
- **Charts** — Daily breakdown, weekday averages, weekly comparison, hourly heatmap, session histograms, cumulative pace, category pie; tasks grouped by category in gradient order across all charts
- **Insight engine** — Auto-generated insights: peak hours, best day, week-over-week delta, streak
- **Calendar tab** — GitHub-style 52-week contribution heat map + 7-column week timeline; click to add, edit, or delete sessions
- **Session management** — Manually add, edit, or delete sessions from the task view or calendar
- **Category colours** — Math-generated HSL gradient palettes per category; recolor any category via the UI
- **Custom date presets** — Save up to 5 custom date-range buttons (fixed range or rolling "since date"); right-click to remove
- **Dark / light theme** — Toggle in the top bar
- **Auto-reload** — DB reloads in the background every 30 seconds; selected date range is preserved across reloads
- **Update notifications** — Checks GitHub releases on startup and shows a button when a newer version is available

## Distribution

Download the latest `TimeTracker.exe` from [Releases](https://github.com/Liam-Hauser/Time_Tracker/releases/latest). No install, no Python required.

Data is stored at `%LOCALAPPDATA%\TimeTracker\timetracker.db`. Custom date presets are stored alongside it in `custom_presets.json`. Replacing the exe with a newer version preserves all existing data.

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

## Project structure

```
time_tracker/
├── version.py              # VERSION constant and GITHUB_REPO
├── icon.png                # Application icon (512×512)
├── fonts/                  # Bundled Geist and Geist Mono TTF files
├── core/
│   ├── models.py           # Task, Session, GoalSpec dataclasses; HSL colour generation
│   ├── db_store.py         # DBStore — thread-safe SQLite reads and writes
│   ├── parser.py           # ParseResult container (returned by DBStore.load)
│   ├── analytics.py        # RangeStats, InsightEngine, TaskSessionStats
│   └── user_presets.py     # CustomPreset — persistent custom date-range presets
├── ui/
│   ├── main_window.py      # MainWindow — sidebar navigation, session bar, timers
│   ├── tab_widgets.py      # CategoryTabWidget, TaskTabWidget
│   ├── calendar_widget.py  # CalendarWidget — contribution graph + week timeline
│   ├── goals_tab.py        # GoalsTab — goal cards grid with KPI header
│   ├── widgets.py          # Reusable components: MetricCard, PresetBar, RangeSlider, …
│   ├── theme.py            # Design tokens, SS stylesheet factory, dark/light toggle
│   └── dialogs/
│       ├── base.py             # BaseFormDialog with shared styling
│       ├── goal_dialogs.py     # AddGoalDialog, EditGoalDialog
│       ├── task_dialogs.py     # NewTaskDialog, RenameTaskDialog, MoveTaskDialog
│       ├── category_dialogs.py # NewCategoryDialog, RenameCategoryDialog, RecolorCategoryDialog
│       ├── session_dialogs.py  # AddSessionDialog, EditSessionDialog
│       └── preset_dialog.py    # AddCustomPresetDialog
├── charts/
│   └── panels.py           # QPainter chart panels (area, bar, heatmap, pie, …)
database/
├── db.py                   # SQLAlchemy engine + SessionLocal (SQLite)
├── migrate.py              # Runs Alembic on startup; stamps existing DBs automatically
├── models/                 # ORM models: Task, HistoricClock, CurrentClock, Category, Goal
└── alembic/                # Migration scripts
run.py                      # Entry point — loads fonts, creates QApplication, launches MainWindow
build.py                    # PyInstaller build + zip script
requirements.txt
```

## Database schema

| Table | Key columns |
|---|---|
| `tasks` | `id`, `name`, `category`, `color`, `archived` |
| `historic_clocks` | `id`, `tasks_id`, `start_time`, `end_time`, `total_sec` |
| `current_clocks` | `id`, `task_id`, `start_time` — one row = active session |
| `categories` | `id`, `name`, `colour_tag` |
| `goals` | `id`, `tasks_id`, `target_hours`, `by_date`, `completed_on`, `archived` |
