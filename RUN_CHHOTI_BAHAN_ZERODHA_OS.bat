@echo off
TITLE Zerodha OS V8.2 — Chhoti Bahan Updated Edition
COLOR 0A
cd /d "%~dp0"

echo ===================================================================
echo   🌸 ZERODHA OS V8.2 — CHHOTI BAHAN UPDATED PRODUCTION EDITION
echo   * Directional M-Units (M1-M4) with Automatic Live Price Polling
echo   * W1 Weekly Option Selling (2-Hour SuperTrend Asymmetric Dual-Expiry)
echo   * Pure Option Price Decay OS Engine (OS1-OS5)
echo   * MCX Commodities Futures + Equity 200 DMA Scanners
echo ===================================================================
echo   1. Starting Background Engine...
start "Zerodha V8.2 Trading Engine (Chhoti Bahan)" /min python main.py

echo   2. Starting Streamlit Dashboard on Port 9007...
echo   Dashboard will open in your default browser at: http://localhost:9007
echo ===================================================================

timeout /t 2 >nul
start "" "http://localhost:9007"
python -m streamlit run app.py --server.port 9007 --server.headless true --browser.gatherUsageStats false

pause
