@echo off
TITLE Zerodha OS V3.0 — Option Selling ^& Commodities
COLOR 0A
cd /d "%~dp0"

echo ===================================================================
echo   ZERODHA OS V3.0 — AUTONOMOUS POD TRADING ENGINE
echo ===================================================================
echo   1. Starting Background Trading Engine...
start "Zerodha V3 Trading Engine" /min python main.py

echo   2. Starting Streamlit Dashboard on Port 9007...
echo   Dashboard will open in your default browser at: http://localhost:9007
echo ===================================================================

timeout /t 2 /nobreak >nul
start "" "http://localhost:9007"
python -m streamlit run app.py --server.port 9007 --server.headless true --browser.gatherUsageStats false

pause
