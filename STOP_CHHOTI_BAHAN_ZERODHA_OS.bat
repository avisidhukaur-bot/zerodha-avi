@echo off
TITLE Stop Zerodha OS V8.2 — Chhoti Bahan Edition
COLOR 0C
cd /d "%~dp0"

echo Stopping Zerodha V8.2 Engine and Dashboard...
taskkill /F /FI "WINDOWTITLE eq Zerodha V8.2 Trading Engine (Chhoti Bahan)*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Zerodha V5.2 Trading Engine*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Zerodha V3 Trading Engine*" /T >nul 2>&1
taskkill /F /IM streamlit.exe >nul 2>&1
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *streamlit*" >nul 2>&1

echo All services stopped cleanly.
timeout /t 3
