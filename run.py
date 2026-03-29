#!/usr/bin/env python3
"""
run.py — Launch the Time Tracker GUI.

Usage:
    python run.py
    python run.py /path/to/vault/2026-Q1.md
"""

import sys
from pathlib import Path

# High-DPI + platform setup before QApplication
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

app = QApplication(sys.argv)
app.setApplicationName("Time Tracker")

# Optional: override vault path from CLI
if len(sys.argv) > 1:
    import time_tracker.ui.main_window as _mw
    _mw.DEFAULT_PATH = Path(sys.argv[1])

from time_tracker.ui.main_window import MainWindow

def main() -> None:
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
