@echo off
TITLE Chhoti Bahan Zerodha OS Auto-Update & Repair
COLOR 0B
cd /d "%~dp0"

echo ===================================================================
echo   🌸 ZERODHA OS V8.2 — CHHOTI BAHAN AUTO-UPDATE & REPAIR
echo ===================================================================
echo   Running automated database migration, package verify and integrity checks...
echo.

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo   [WARN] Pip install encountered an issue, proceeding with update...
)

python chhoti_bahan_auto_update.py

echo.
echo ===================================================================
echo   Auto-update finished! Press any key to close this window.
echo ===================================================================
pause
