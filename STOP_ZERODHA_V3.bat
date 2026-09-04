@echo off
TITLE Stop Zerodha OS V3.0
COLOR 0C
cd /d "%~dp0"

echo ===================================================================
echo   Stopping Zerodha OS V3.0 processes...
echo ===================================================================

taskkill /F /FI "WINDOWTITLE eq Zerodha V3 Trading Engine*" /T >nul 2>&1
taskkill /F /IM streamlit.exe >nul 2>&1

echo.
echo ✅ All Zerodha OS V3.0 processes stopped.
timeout /t 3 >nul
