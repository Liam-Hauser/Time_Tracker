#!/usr/bin/env python3
"""
run.py — Launch the Time Tracker GUI.

Usage:
    python run.py
"""

import sys

# High-DPI + platform setup before QApplication
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

app = QApplication(sys.argv)
app.setApplicationName("Time Tracker")

from time_tracker.ui.main_window import MainWindow

def main() -> None:
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
