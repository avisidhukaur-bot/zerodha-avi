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

# ─────────────────────────────────────────────────────────────────────────────
# NSE Trading Holiday Calendar (2026 - 2027) & Weekend Check
# ─────────────────────────────────────────────────────────────────────────────
NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-20",  # Id-Ul-Fitr (Ramzan Id)
    "2026-03-27",  # Shri Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id / Eid-Ul-Adha
    "2026-06-26",  # Muharram
    "2026-08-15",  # Independence Day
    "2026-09-04",  # Milad-un-Nabi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    # "2026-11-09",  # Removed: NSE is active today (09-Nov-2026)
    "2026-11-10",  # Diwali Balipratipada
    "2026-11-24",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas
}

def is_trading_day(dt: datetime.datetime = None) -> bool:
    """
    Returns True ONLY if dt (or current IST datetime) is an active NSE trading day.
    Strictly returns False for Saturdays (5), Sundays (6), and all official NSE holidays.
    """
    if dt is None:
        dt = ist_now()
    # Check weekend (0 = Monday ... 4 = Friday, 5 = Saturday, 6 = Sunday)
    if dt.weekday() >= 5:
        return False
    # Check NSE holiday list
    day_str = dt.strftime("%Y-%m-%d")
    if day_str in NSE_HOLIDAYS_2026:
        return False
    # Also check if custom holiday is registered in DB
    try:
        custom_holidays = db.get("custom_trading_holidays", "")
        if custom_holidays and day_str in [h.strip() for h in custom_holidays.split(",")]:
            return False
    except Exception:
        pass
    return True

def is_market_hours() -> bool:
    """Returns True if the current IST time is within active NSE market hours (09:15 to 15:30) on a trading day."""
    now = ist_now()
    if not is_trading_day(now):
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def is_market_session_active(dt: datetime.datetime = None) -> bool:
    """
    V7.0 Super Sukhoi Market Session Guard:
    Returns True ONLY during active trading hours (09:15 to 15:30 IST) on valid NSE trading days.
    Guarantees zero alert spam and peaceful sleep during weekends, holidays, and off-hours.
    """
    if dt is None:
        dt = ist_now()
    if not is_trading_day(dt):
        return False
    market_open  = dt.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = dt.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= dt <= market_close


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
