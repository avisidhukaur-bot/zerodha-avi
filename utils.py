"""
utils.py — Zerodha Option Selling App | Logging & Telegram Alerts Utilities
"""
import requests
import datetime
import pytz
import os
import db
import config as cfg

def ist_now() -> datetime.datetime:
    """Returns current datetime in IST timezone."""
    return datetime.datetime.now(pytz.timezone('Asia/Kolkata'))

# Alias for compatibility
now_ist = ist_now

def is_market_hours() -> bool:
    """Returns True if the current IST time is within NSE market hours (09:15 to 15:30)."""
    now = ist_now()
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def log(msg: str, level: str = "INFO") -> None:
    """Logs a message to the console and to the log file."""
    timestamp = ist_now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level.upper()}] {msg}"
    print(formatted)

    try:
        with open(cfg.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def send_telegram(msg: str) -> bool:
    """Sends a Telegram alert using credentials stored in DB."""
    if db.get("NOTIFICATIONS_ENABLED", "YES") != "YES":
        return False
    if db.get("TELEGRAM_ALERTS_ENABLED", "YES") != "YES":
        return False
    token   = db.get("TELEGRAM_TOKEN")
    chat_id = db.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"⚡ <b>{cfg.SYSTEM_NAME}</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n{msg}",
        "parse_mode": "HTML"
    }

    try:
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code == 200:
            return True
        else:
            log(f"Telegram alert failed: {resp.status_code} {resp.text}", "WARN")
    except Exception as e:
        log(f"Telegram alert exception: {e}", "WARN")

    return False
