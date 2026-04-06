"""
build.py — Build TimeTracker.exe and TimeTrackerDebug.exe, then zip the release.

Usage:
    python build.py           # build both
    python build.py --release # release only
    python build.py --debug   # debug only
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT     = Path(__file__).parent
DIST     = ROOT / "dist"
EXE      = DIST / "TimeTracker.exe"
DEBUG_EXE = DIST / "TimeTrackerDebug.exe"
ZIP      = DIST / "TimeTracker.zip"

args = sys.argv[1:]
build_release = "--debug" not in args
build_debug   = "--release" not in args


def run_pyinstaller(spec: str) -> None:
    print(f"Building {spec}...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print(f"PyInstaller failed for {spec}.")
        sys.exit(1)


if build_release:
    run_pyinstaller("TimeTracker.spec")
    print("Zipping release...")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(EXE, "TimeTracker.exe")
    size_mb = ZIP.stat().st_size / 1_048_576
    print(f"Release done — dist/TimeTracker.zip ({size_mb:.1f} MB)")

if build_debug:
    run_pyinstaller("TimeTrackerDebug.spec")
    size_mb = DEBUG_EXE.stat().st_size / 1_048_576
    print(f"Debug done  — dist/TimeTrackerDebug.exe ({size_mb:.1f} MB)")
