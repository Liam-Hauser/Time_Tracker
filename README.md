# Time Tracker

A PyQt5 desktop application for detailed time tracking and analytics. Time data is stored as `[clock::START--END]` annotations in an Obsidian-compatible markdown vault file, keeping records human-readable, portable, and version-controllable.

## Features

- **Task management** — Parse tasks from markdown with color tags (`#blue`, `#red`, etc.)
- **Clock in/out** — Start and stop timing sessions directly from the UI
- **Live elapsed time** — Active session timer updates every second
- **Goal tracking** — Set target hours and deadlines per task with pace calculations
- **Analytics dashboards** — Daily breakdown, weekday averages, weekly comparison, hourly heatmap
- **Insight engine** — Auto-generated insights (streaks, peak hours, best day, goal pace)
- **Auto-reload** — Vault file reloads in the background every 30 seconds

## Requirements

- Python 3.9+
- PyQt5
- numpy

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python run.py
```

Or point it at a specific vault file:

```bash
python run.py /path/to/vault/2026-Q1.md
```

The default vault path can also be changed via the path input and Browse button in the app's top bar.

## Project Structure

```
time_tracker/
├── core/
│   ├── models.py       # Task, Session, GoalSpec dataclasses
│   ├── parser.py       # VaultParser / VaultWriter (thread-safe file I/O)
│   └── analytics.py    # RangeStats, GoalTracker, InsightEngine
├── ui/
│   ├── main_window.py  # Top-level QMainWindow and layout
│   ├── widgets.py      # Reusable components (MetricCard, TaskRow, etc.)
│   └── theme.py        # Color palette and constants
├── charts/
│   └── panels.py       # Chart panels (stacked area, weekday bar, heatmap, etc.)
run.py                  # Entry point
requirements.txt
```

## Data Format

Tasks are stored in a markdown file as standard checkbox items with inline clock annotations:

```markdown
- [ ] Learn Python #blue [clock::2026-03-30T09:00:00--2026-03-30T10:30:00]
- [ ] Code review #green [clock::2026-03-30T11:00:00--]
```

An open session (no end time) means the task is currently clocked in.
