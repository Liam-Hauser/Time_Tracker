"""
build.py — Build TimeTracker.exe and zip it for release.

Usage:
    python build.py
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
EXE  = ROOT / "dist" / "TimeTracker.exe"
ZIP  = ROOT / "dist" / "TimeTracker.zip"

print("Building exe...")
result = subprocess.run(
    [sys.executable, "-m", "PyInstaller", "TimeTracker.spec"],
    cwd=ROOT,
)
if result.returncode != 0:
    print("PyInstaller failed.")
    sys.exit(1)

print("Zipping...")
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(EXE, "TimeTracker.exe")

size_mb = ZIP.stat().st_size / 1_048_576
print(f"Done — dist/TimeTracker.zip ({size_mb:.1f} MB)")
