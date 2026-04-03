#!/usr/bin/env python3
"""
run.py — Launch the Time Tracker GUI.

Usage:
    python run.py
"""

import sys
from pathlib import Path

# High-DPI + platform setup before QApplication
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPainter, QPainterPath

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

app = QApplication(sys.argv)
app.setApplicationName("Time Tracker")

# ── Database setup ────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import QMessageBox, QSplashScreen
from PyQt5.QtGui import QPixmap as _QPixmap

_splash_px = _QPixmap(1, 1)
_splash_px.fill(Qt.transparent)
_splash = QSplashScreen(_splash_px)
_splash.showMessage("Applying database migrations…", Qt.AlignCenter, Qt.white)
_splash.show()
app.processEvents()

try:
    from database.migrate import run_pending_migrations
    run_pending_migrations()
except Exception as _mig_err:
    _splash.hide()
    QMessageBox.critical(
        None,
        "Database error",
        f"Could not initialise the database:\n\n{_mig_err}",
    )
    sys.exit(1)

_splash.hide()

def _make_rounded_icon(path: Path, radius_ratio: float = 0.18) -> QIcon:
    """Return a QIcon clipped to a rounded rectangle."""
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtCore import QRectF
    px = QPixmap(str(path))
    if px.isNull():
        return QIcon()
    w, h = px.width(), px.height()
    r = min(w, h) * radius_ratio
    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    pp = QPainterPath()
    pp.addRoundedRect(QRectF(0, 0, w, h), r, r)
    painter.setClipPath(pp)
    painter.drawPixmap(0, 0, px)
    painter.end()
    return QIcon(out)

_icon_path = Path(__file__).parent / "time_tracker" / "icon.png"
if _icon_path.exists():
    app.setWindowIcon(_make_rounded_icon(_icon_path))

from time_tracker.ui.main_window import MainWindow

def main() -> None:
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()