@echo off
TITLE Zerodha OS V5.0 "Old & Gold" — Option Selling & Commodities
COLOR 0B
cd /d "%~dp0"

echo ===================================================================
echo   ZERODHA OS V5.0 "OLD & GOLD" ARCHITECTURE
echo   Unified Console • Decoupled M1 Anchor • 3:00 PM Continuation
echo ===================================================================
echo   1. Initializing & Migrating Database...
python -c "import db; db.init_db(); print('Database V5 Migrations verified.')"

echo   2. Starting Background Trading Engine...
start "Zerodha V5 Trading Engine" /min python main.py

echo   3. Starting Streamlit Dashboard on Port 9007...
echo   Dashboard opening at: http://localhost:9007
echo ===================================================================

timeout /t 2 /nobreak >nul
start "" "http://localhost:9007"
python -m streamlit run app.py --server.port 9007 --server.headless true --browser.gatherUsageStats false

pause
