@echo off
title GestureSense
cd /d "%~dp0"

echo =========================================
echo   GestureSense v2 — Hand Gesture Control
echo =========================================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

REM ── Activate venv if present ───────────────────────────────────────────────
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [INFO] No venv found — using system Python.
)

REM ── Install / verify dependencies ─────────────────────────────────────────
echo [INFO] Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARN] Some packages may not have installed correctly.
)

echo.
echo [INFO] Launching GestureSense...
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] GestureSense exited with an error. See above for details.
    pause
)
