@echo off
TITLE Zerodha OS V3.0 — 1-Click Auto Repair & Upgrade
COLOR 0B
cd /d "%~dp0"

echo ===================================================================
echo   ZERODHA OS V3.0 — SISTER'S LAPTOP 1-CLICK AUTO REPAIR & UPGRADE
echo ===================================================================
echo   This will:
echo   1. Backup your existing secrets.txt credentials and database
echo   2. Clean out corrupted changes & restore official V3.0 codebase
echo   3. Run SQLite database schema migrations
echo   4. Install/Verify Python dependencies
echo   5. Generate 1-Click RUN_ZERODHA_V3.bat launcher
echo ===================================================================
echo.

python sister_v3_auto_repair.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Python execution failed. Please check if Python is installed and in PATH.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Press any key to exit this installer...
pause >nul
