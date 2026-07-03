"""
telegram_bot.py -- Zerodha OptionSelling Engine | Brick 5
========================================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 5)
Date     : June 2026

ALERT SYSTEM via Telegram Bot API.
Sends real-time trading notifications to the operator.

ALERT TYPES (per Blueprint):
  1. Strike Executed    -- on every order placement
  2. Strike Closed      -- on every exit (sell + hedge)
  3. Block Daily Summary-- scheduled morning/EOD
  4. Portfolio Summary  -- full P&L snapshot on demand
  5. Engine Status      -- startup / shutdown / errors
  6. IP Guard Violation -- security alert
  7. Rollover Alert     -- Monday hedge rollover events
  8. Error / URGENT     -- failed orders needing manual action

CREDENTIALS (from secrets.txt):
  TELEGRAM_TOKEN   = 8600742889:AAGUn2v7aAkYGUKXKxoPaeLSQNPFGBUEhGE
  TELEGRAM_CHAT_ID = 586422450

API: https://api.telegram.org/bot<TOKEN>/sendMessage
     parse_mode=HTML (supports <b>, <i>, <code> tags)

ANTI-SPAM: 30-second cooldown per message type.
           Prevents duplicate alerts on fast market moves.
"""

import sys
import time
import requests
import threading
from datetime import datetime
from typing import Optional
import pytz

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg

IST = pytz.timezone("Asia/Kolkata")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ─────────────────────────────────────────────────────────────────────────────
# Internal state
# ─────────────────────────────────────────────────────────────────────────────
_cooldown_map: dict  = {}   # {alert_key: last_sent_timestamp}
_cooldown_lock       = threading.Lock()
DEFAULT_COOLDOWN_SEC = 30   # seconds between identical alert types


def _ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _ist_time() -> str:
    return datetime.now(IST).strftime("%H:%M:%S")


def _log(msg: str, level: str = "INFO") -> None:
    print(f"[TELEGRAM][{level}] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# CORE SEND FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def send_ntfy(message: str) -> bool:
    """Sends a push notification to mobile via ntfy.sh."""
    if db.get("NTFY_ALERTS_ENABLED", "YES") != "YES":
        _log("Ntfy alerts are disabled. Skipping Ntfy notification.", "INFO")
        return False
    topic = db.get("NTFY_TOPIC", "").strip()
    if not topic or topic.upper() in ("YOUR_NTFY_TOPIC_HERE", "TOPIC", ""):
        return False
    try:
        import re
        clean_text = re.sub(r'<[^>]+>', '', message)
        headers = {
            "Title": "Zerodha OS Alert",
            "Tags": "chart_with_upwards_trend,moneybag",
            "Priority": "default"
        }
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=clean_text.encode("utf-8"),
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            _log(f"Ntfy alert sent successfully to topic: {topic}")
            return True
        else:
            _log(f"Ntfy API error: HTTP {resp.status_code} -> {resp.text}", "ERROR")
            return False
    except Exception as e:
        _log(f"Exception sending Ntfy alert: {e}", "ERROR")
        return False


def send(
    message:      str,
    alert_key:    str  = None,
    cooldown_sec: int  = DEFAULT_COOLDOWN_SEC,
    force:        bool = False,
) -> bool:
    """
    Sends alerts to configured channels (Telegram and/or ntfy).
    """
    # Check if alerts are globally enabled
    if db.get("NOTIFICATIONS_ENABLED", "YES") != "YES":
        _log("Alerts are disabled. Skipping Telegram/Ntfy notification.", "INFO")
        return False

    # Cooldown check
    if alert_key and not force:
        with _cooldown_lock:
            last_sent = _cooldown_map.get(alert_key, 0)
            elapsed   = time.time() - last_sent
            if elapsed < cooldown_sec:
                remaining = int(cooldown_sec - elapsed)
                _log(f"Cooldown: {alert_key} ({remaining}s remaining). Skipping.", "COOLDOWN")
                return False

    telegram_sent = False
    ntfy_sent = False

    token   = db.get("TELEGRAM_TOKEN", "")
    chat_id = db.get("TELEGRAM_CHAT_ID", "")

    # 1. Attempt Telegram
    if db.get("TELEGRAM_ALERTS_ENABLED", "YES") == "YES":
        if token and chat_id:
            try:
                url  = TELEGRAM_API.format(token=token)
                data = {
                    "chat_id":                  chat_id,
                    "text":                     message,
                    "parse_mode":               "HTML",
                    "disable_web_page_preview": True,
                }
                resp = requests.post(url, data=data, timeout=10)
                if resp.status_code == 200 and resp.json().get("ok"):
                    telegram_sent = True
                    _log(f"Telegram Alert sent: {alert_key or 'message'[:50]}")
                else:
                    err = resp.json().get("description", resp.text)
                    _log(f"Telegram API error: {err}", "ERROR")
            except Exception as e:
                _log(f"Exception sending Telegram alert: {e}", "ERROR")
        else:
            _log("Telegram not configured. Skipping Telegram delivery.", "DEBUG")
    else:
        _log("Telegram alerts are disabled. Skipping Telegram notification.", "INFO")

    # 2. Attempt Ntfy
    ntfy_sent = send_ntfy(message)

    # If any channel succeeded, update cooldown map and return True
    if telegram_sent or ntfy_sent:
        if alert_key:
            with _cooldown_lock:
                _cooldown_map[alert_key] = time.time()
        return True

    _log("No alerts could be delivered (Telegram and Ntfy both skipped or failed).", "WARN")
    return False


def send_silent(message: str) -> bool:
    """Sends a message ignoring cooldowns — for critical alerts only."""
    return send(message, alert_key=None, force=True)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 1: STRIKE EXECUTED (per Blueprint format)
# ─────────────────────────────────────────────────────────────────────────────

def alert_strike_executed(
    block_number:  int,
    expiry_date:   str,
    strike_price:  int,
    option_type:   str,
    leg_type:      str,
    lots:          int,
    anchor_price:  float,
    order_id:      str,
    fill_price:    float = 0.0,
) -> bool:
    """
    Sends alert when a strike order is placed and filled.

    Blueprint format:
    ZERODHA OS
    Block 1 | Expiry: 26-Jun-2025
    Strike: 24000 CE SELL
    Lots: 2 | Anchor: Rs120.00
    Status: ORDER PLACED
    Order ID: #KITE12345
    """
    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    qty      = lots * lot_size
    leg_icon = "SELL" if leg_type == "SELL" else "HEDGE BUY"
    mode     = "[PAPER]" if db.get("paper_mode", "YES") == "YES" else ""

    msg = (
        f"<b>ZERODHA OS {mode}</b>\n"
        f"<b>ORDER PLACED</b>\n"
        f"{'='*25}\n"
        f"Block {block_number} | Expiry: {expiry_date}\n"
        f"Strike: <b>{strike_price} {option_type} {leg_icon}</b>\n"
        f"Lots: {lots} | Qty: {qty}\n"
        f"Anchor: Rs{anchor_price:.2f}"
        + (f" | Fill: Rs{fill_price:.2f}" if fill_price > 0 else "") +
        f"\nStatus: <b>ORDER PLACED</b>\n"
        f"Order ID: <code>{order_id}</code>\n"
        f"Time: {_ist_time()}"
    )

    return send(
        msg,
        alert_key    = f"executed_{block_number}_{strike_price}_{option_type}_{leg_type}",
        cooldown_sec = 60,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 2: STRIKE CLOSED (per Blueprint format)
# ─────────────────────────────────────────────────────────────────────────────

def alert_strike_closed(
    block_number:     int,
    strike_price:     int,
    option_type:      str,
    sell_anchor:      float,
    sell_exit_price:  float,
    hedge_anchor:     float,
    hedge_exit_price: float,
    realized_pnl:     float,
) -> bool:
    """
    Sends alert when a strike + hedge are closed together.

    Blueprint format:
    STRIKE CLOSED
    Block 1 | 24500 CE SELL + Hedge
    Sell Exit: Rs45.00 (was Rs75.00)
    Hedge Exit: Rs18.00 (was Rs40.00)
    Net P&L: +Rs3,750
    """
    mode     = "[PAPER] " if db.get("paper_mode", "YES") == "YES" else ""
    pnl_sign = "+" if realized_pnl >= 0 else ""
    pnl_icon = "PROFIT" if realized_pnl >= 0 else "LOSS"

    msg = (
        f"<b>{mode}STRIKE CLOSED -- {pnl_icon}</b>\n"
        f"{'='*25}\n"
        f"Block {block_number} | <b>{strike_price} {option_type} SELL + Hedge</b>\n"
        f"Sell Exit: Rs{sell_exit_price:.2f} (was Rs{sell_anchor:.2f})\n"
        f"Hedge Exit: Rs{hedge_exit_price:.2f} (was Rs{hedge_anchor:.2f})\n"
        f"{'='*25}\n"
        f"<b>Net P&amp;L: {pnl_sign}Rs{abs(realized_pnl):,.2f}</b>\n"
        f"Time: {_ist_time()}"
    )

    return send(
        msg,
        alert_key    = f"closed_{block_number}_{strike_price}_{option_type}",
        cooldown_sec = 5,
        force        = True,  # Always send close alerts
    )


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 3: BLOCK DAILY SUMMARY (per Blueprint format)
# ─────────────────────────────────────────────────────────────────────────────

def alert_block_daily_summary(block_pnl: dict) -> bool:
    """
    Sends per-block daily P&L summary.

    Blueprint format:
    BLOCK 1 DAILY SUMMARY
    Expiry: 26-Jun-2025 (Monthly)
    ========================
    24000 CE SELL:  +Rs4,250
    24000 PE SELL:  +Rs2,100
    24500 CE Hedge: -Rs1,200
    ========================
    Block P&L: +Rs5,150
    """
    block_num  = block_pnl.get("block_number", "?")
    expiry     = block_pnl.get("expiry_date", "")
    exp_type   = block_pnl.get("expiry_type", "").title()
    total_pnl  = block_pnl.get("total_pnl", 0.0)
    strikes    = block_pnl.get("strike_pnls", [])
    mode       = "[PAPER] " if db.get("paper_mode", "YES") == "YES" else ""

    lines = [
        f"<b>{mode}BLOCK {block_num} DAILY SUMMARY</b>",
        f"Expiry: {expiry} ({exp_type})",
        "=" * 28,
    ]

    for s in strikes:
        ltp_avail = s.get("ltp_available", False)
        if not ltp_avail:
            pnl_str = "--"
        else:
            pnl     = s["pnl"]
            sign    = "+" if pnl >= 0 else "-"
            pnl_str = f"{sign}Rs{abs(pnl):,.0f}"

        leg_label = "SELL" if s["leg_type"] == "SELL" else "Hedge"
        label     = f"{s['strike_price']} {s['option_type']} {leg_label}"
        lines.append(f"{label}: <b>{pnl_str}</b>")

    lines.append("=" * 28)

    sign      = "+" if total_pnl >= 0 else "-"
    pnl_icon  = "PROFIT" if total_pnl >= 0 else "LOSS"
    lines.append(
        f"<b>Block P&amp;L: {sign}Rs{abs(total_pnl):,.2f} -- {pnl_icon}</b>"
    )

    msg = "\n".join(lines)

    return send(
        msg,
        alert_key    = f"daily_summary_block_{block_num}",
        cooldown_sec = 3600,  # Max once per hour
    )


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 4: PORTFOLIO SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def alert_portfolio_summary(portfolio_pnl: dict) -> bool:
    """
    Sends full portfolio P&L summary.
    Shows each block + grand total.
    """
    total       = portfolio_pnl.get("total_pnl", 0.0)
    blocks      = portfolio_pnl.get("block_pnls", [])
    updated_at  = portfolio_pnl.get("last_updated", _ist_now())
    mode        = "[PAPER] " if db.get("paper_mode", "YES") == "YES" else ""
    pnl_icon    = "PROFIT" if total >= 0 else "LOSS"

    lines = [
        f"<b>{mode}ZERODHA OS -- PORTFOLIO SUMMARY</b>",
        f"Time: {updated_at}",
        "=" * 35,
    ]

    for bp in blocks:
        bpnl    = bp.get("total_pnl", 0.0)
        sign    = "+" if bpnl >= 0 else "-"
        n_open  = bp.get("open_strikes", 0)
        lines.append(
            f"Block {bp['block_number']} ({bp['expiry_date']}): "
            f"<b>{sign}Rs{abs(bpnl):,.2f}</b>  [{n_open} open strikes]"
        )

    lines.append("=" * 35)
    sign  = "+" if total >= 0 else "-"
    lines.append(
        f"<b>TOTAL PORTFOLIO P&amp;L: {sign}Rs{abs(total):,.2f} -- {pnl_icon}</b>"
    )

    if portfolio_pnl.get("paper_mode"):
        lines.append("\n<i>[Paper Mode -- LTP not available]</i>")

    msg = "\n".join(lines)

    return send(
        msg,
        alert_key    = "portfolio_summary",
        cooldown_sec = 300,  # Max once per 5 min
    )


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 5: ENGINE STATUS
# ─────────────────────────────────────────────────────────────────────────────

def alert_engine_started() -> bool:
    """Sent when engine starts successfully."""
    mode = "PAPER TRADING" if db.get("paper_mode", "YES") == "YES" else "LIVE TRADING"
    msg  = (
        f"<b>ZERODHA OS ENGINE STARTED</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Port: 9007\n"
        f"Time: {_ist_now()}\n"
        f"Lot Size: {db.get('lot_size', '65')} | "
        f"Interval: {db.get('check_interval', '1800')}s"
    )
    return send(msg, alert_key="engine_started", cooldown_sec=60)


def alert_engine_stopped(reason: str = "Manual stop") -> bool:
    """Sent when engine stops."""
    msg = (
        f"<b>ZERODHA OS ENGINE STOPPED</b>\n"
        f"Reason: {reason}\n"
        f"Time: {_ist_now()}"
    )
    return send_silent(msg)


def alert_login_success() -> bool:
    """Sent after successful Kite API login."""
    msg = (
        f"<b>ZERODHA KITE LOGIN OK</b>\n"
        f"Access token obtained (valid 24hrs)\n"
        f"Time: {_ist_now()}"
    )
    return send(msg, alert_key="login_success", cooldown_sec=3600)


def alert_login_failed(reason: str = "") -> bool:
    """Sent when Kite API login fails."""
    msg = (
        f"<b>ZERODHA KITE LOGIN FAILED</b>\n"
        f"Reason: {reason or 'Check password/TOTP key in secrets.txt'}\n"
        f"Action: Fill KITE_PASSWORD + KITE_TOTP_KEY and restart\n"
        f"Time: {_ist_now()}"
    )
    return send(msg, alert_key="login_failed", cooldown_sec=1800)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 6: IP GUARD VIOLATION
# ─────────────────────────────────────────────────────────────────────────────

def alert_ip_guard_violation(current_ip: str, allowed_ip: str) -> bool:
    """
    Sent when IP guard detects wrong IP.
    Trading is paused until correct VPN IP is active.
    """
    msg = (
        f"<b>IP GUARD VIOLATION</b>\n"
        f"Current IP: <code>{current_ip}</code>\n"
        f"Whitelisted: <code>{allowed_ip}</code>\n"
        f"Action: Connect VPN ({allowed_ip}) to resume trading\n"
        f"Time: {_ist_now()}"
    )
    return send(msg, alert_key="ip_guard", cooldown_sec=3600)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 7: ROLLOVER
# ─────────────────────────────────────────────────────────────────────────────

def alert_rollover_started(block_number: int, old_hedge: str, new_expiry: str) -> bool:
    """Sent when Monday hedge rollover begins."""
    msg = (
        f"<b>MONDAY HEDGE ROLLOVER STARTED</b>\n"
        f"Block {block_number} | Old Hedge: {old_hedge}\n"
        f"Rolling to expiry: {new_expiry}\n"
        f"Time: {_ist_time()}"
    )
    return send(msg, alert_key=f"rollover_start_{block_number}", cooldown_sec=60)


def alert_rollover_complete(
    block_number:   int,
    old_symbol:     str,
    new_symbol:     str,
    new_expiry:     str,
) -> bool:
    """Sent when Monday hedge rollover completes successfully."""
    msg = (
        f"<b>ROLLOVER COMPLETED</b>\n"
        f"Block {block_number}\n"
        f"{'='*25}\n"
        f"Old Hedge Closed: <code>{old_symbol}</code>\n"
        f"New Hedge Opened: <code>{new_symbol}</code>\n"
        f"New Expiry: {new_expiry}\n"
        f"Time: {_ist_time()}"
    )
    return send(msg, alert_key=f"rollover_done_{block_number}", cooldown_sec=60)


def alert_rollover_failed(block_number: int, reason: str) -> bool:
    """Sent when rollover fails — needs manual intervention."""
    msg = (
        f"<b>ROLLOVER FAILED -- URGENT</b>\n"
        f"Block {block_number}\n"
        f"Reason: {reason}\n"
        f"Action: Manual hedge rollover required!\n"
        f"Time: {_ist_time()}"
    )
    return send_silent(msg)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 8: ORDER ERRORS (URGENT)
# ─────────────────────────────────────────────────────────────────────────────

def alert_order_failed(
    action:  str,
    symbol:  str,
    qty:     int,
    reason:  str = "",
) -> bool:
    """
    URGENT alert when an order fails to place or fill.
    Always sent immediately (no cooldown).
    """
    msg = (
        f"<b>ORDER FAILED -- URGENT ACTION REQUIRED</b>\n"
        f"Action: {action}\n"
        f"Symbol: <code>{symbol}</code>\n"
        f"Qty: {qty}\n"
        f"Reason: {reason or 'Order rejected or did not fill'}\n"
        f"Time: {_ist_time()}\n"
        f"<b>Check Zerodha OS dashboard immediately!</b>"
    )
    return send_silent(msg)


def alert_naked_short_risk(block_number: int, strike_price: int, option_type: str) -> bool:
    """
    CRITICAL: Sent when hedge is open but sell failed —
    or sell is covered but hedge failed to close.
    Requires immediate manual action.
    """
    msg = (
        f"<b>CRITICAL: NAKED SHORT RISK</b>\n"
        f"Block {block_number} | {strike_price} {option_type}\n"
        f"Position may be unhedged!\n"
        f"Time: {_ist_time()}\n"
        f"<b>IMMEDIATE MANUAL ACTION REQUIRED</b>"
    )
    return send_silent(msg)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 9: BLOCK EXPIRY
# ─────────────────────────────────────────────────────────────────────────────

def alert_block_expired(block_number: int, expiry_date: str) -> bool:
    """Sent when a block is auto-expired at end of expiry date."""
    msg = (
        f"<b>BLOCK EXPIRED</b>\n"
        f"Block {block_number} | Expiry: {expiry_date}\n"
        f"Status: EXPIRED\n"
        f"Action: Review and archive on dashboard\n"
        f"Time: {_ist_now()}"
    )
    return send(msg, alert_key=f"expired_{block_number}", cooldown_sec=60)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT 10: HEARTBEAT (periodic alive signal)
# ─────────────────────────────────────────────────────────────────────────────

def alert_heartbeat(portfolio_pnl: dict) -> bool:
    """
    Periodic heartbeat to confirm engine is alive with detailed position tracking.
    Sent every 15 minutes (configured in main.py).
    """
    mode       = "PAPER" if db.get("paper_mode", "YES") == "YES" else "LIVE"
    total      = portfolio_pnl.get("total_pnl", 0.0)
    pnl_sign   = "+" if total >= 0 else "-"
    pnl_str    = f"{pnl_sign}Rs{abs(total):,.2f}"
    
    n_blocks   = portfolio_pnl.get("active_blocks", 0)
    n_open     = portfolio_pnl.get("total_open_strikes", 0)
    
    lines = [
        f"<b>🏦 ZERODHA OS HEARTBEAT -- {mode}</b>",
        f"Time (IST): {_ist_now()}",
        f"Portfolio P&amp;L: <b>{pnl_str}</b>",
        f"Active Blocks: {n_blocks} | Open Strikes: {n_open}",
        "=" * 30
    ]
    
    buffer_tolerance = float(db.get("buffer_tolerance", "2.0"))
    
    for bp in portfolio_pnl.get("block_pnls", []):
        block_num = bp.get("block_number", "?")
        block_pnl = bp.get("total_pnl", 0.0)
        b_sign = "+" if block_pnl >= 0 else "-"
        lines.append(f"<b>Block {block_num} ({bp.get('expiry_date')}) | PnL: {b_sign}Rs{abs(block_pnl):,.2f}</b>")
        
        # Filter for open strikes in this block
        block_strikes = [s for s in bp.get("strike_pnls", []) if s.get("status") == "OPEN"]
        if not block_strikes:
            lines.append("  <i>No open positions.</i>")
        for s in block_strikes:
            strike_price = s["strike_price"]
            option_type = s["option_type"]
            leg_type = s["leg_type"]
            lots = s["lots"]
            qty = s.get("qty", lots * int(db.get("lot_size", "65")))
            anchor = s["anchor_price"]
            ltp = s["ltp"]
            ltp_avail = s["ltp_available"]
            
            leg_label = "SELL" if leg_type == "SELL" else "Hedge"
            
            if not ltp_avail:
                ltp_str = "--"
                status_str = "⚠️ LTP N/A"
            else:
                ltp_str = f"Rs{ltp:.2f}"
                if leg_type == "SELL":
                    threshold = anchor + buffer_tolerance
                    if ltp >= threshold:
                        status_str = f"🔴 <b>BREACHED</b> (LTP {ltp_str} >= SL Rs{threshold:.2f})"
                    else:
                        status_str = f"🟢 <b>Safe</b> (LTP {ltp_str} &lt; SL Rs{threshold:.2f})"
                else:
                    status_str = f"🛡️ <b>Hedge Active</b> (LTP {ltp_str})"
                    
            lines.append(
                f"  • {strike_price} {option_type} {leg_label} ({lots} Lot/Qty {qty})\n"
                f"    Anchor: Rs{anchor:.2f} | LTP: {ltp_str}\n"
                f"    Status: {status_str}"
            )
        lines.append("-" * 30)
        
    msg = "\n".join(lines)
    return send(msg, alert_key="heartbeat", cooldown_sec=60)  # Max once/hr


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULED DAILY SUMMARY (called by main.py at EOD)
# ─────────────────────────────────────────────────────────────────────────────

def send_all_block_summaries(portfolio_pnl: dict) -> None:
    """
    Sends daily summary for every active block.
    Called by main.py at market close (15:30 IST).
    """
    _log("Sending daily block summaries...", "DAILY")
    for bp in portfolio_pnl.get("block_pnls", []):
        alert_block_daily_summary(bp)
        time.sleep(1)  # Small delay between messages to avoid Telegram rate limit
    alert_portfolio_summary(portfolio_pnl)
    _log("Daily summaries sent.", "DAILY")


# ─────────────────────────────────────────────────────────────────────────────
# TEST CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

def test_telegram_connection() -> dict:
    """
    Sends a test message to verify Telegram config.
    Returns: {"ok": bool, "message": str}
    """
    token   = db.get("TELEGRAM_TOKEN", "")
    chat_id = db.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return {"ok": False, "message": "TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing in secrets.txt."}

    test_msg = (
        f"<b>ZERODHA OS -- TEST ALERT</b>\n"
        f"Alert connection verified!\n"
        f"Chat ID: <code>{chat_id}</code>\n"
        f"Time: {_ist_now()}"
    )

    sent = send_silent(test_msg)
    if sent:
        return {"ok": True, "message": f"Test message sent to chat_id {chat_id}."}
    return {"ok": False, "message": "Failed to send test message. Check token and chat_id."}
