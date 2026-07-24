"""
pnl_engine.py -- Zerodha OptionSelling Engine | Brick 4
======================================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 4)
Date     : June 2026

REAL-TIME P&L CALCULATOR.
Fetches live LTP for all open option strikes and computes:
  - Per-strike unrealized P&L
  - Per-block total P&L
  - Portfolio total P&L (sum of all active blocks)

P&L FORMULAS (exact from Blueprint):
  SELL LEG   : PnL = (Anchor Price - Current LTP) x Lots x Lot Size
  HEDGE_BUY  : PnL = (Current LTP - Anchor Price) x Lots x Lot Size
  Block PnL  : SUM of all strike PnLs in that block
  Portfolio  : SUM of all Block PnLs

LTP SOURCES (in priority order):
  1. Zerodha executor get_ltp() via positions API
  2. Zerodha executor via order book
  3. Cached LTP (if fetch fails, use last known)
  4. 0.0 (fallback -- skipped in P&L)

CACHE: LTP cached per strike_id for 30 seconds.
  Prevents hammering API on every dashboard refresh.

Paper mode: LTP = 0.0 (no API calls).
  Dashboard shows P&L as "--" when LTP unavailable.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Optional
import pytz

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg
from kite_executor import kite_executor

IST = pytz.timezone("Asia/Kolkata")


def _ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str, level: str = "INFO") -> None:
    print(f"[PNL_ENGINE][{level}] {msg}")


_last_exit_check_time = 0.0
_last_exit_check_candle = ""


# ─────────────────────────────────────────────────────────────────────────────
# LTP CACHE
# LTP cached per strike_id with TTL to avoid API spam
# ─────────────────────────────────────────────────────────────────────────────

_ltp_cache: dict = {}       # {strike_id: {"ltp": float, "ts": float, "symbol": str}}
_cache_lock = threading.Lock()
LTP_CACHE_TTL = 30          # seconds -- refresh every 30s


def _get_cached_ltp(strike_id: int) -> Optional[float]:
    """Returns cached LTP if still fresh, else None."""
    with _cache_lock:
        entry = _ltp_cache.get(strike_id)
        if entry and (time.time() - entry["ts"]) < LTP_CACHE_TTL:
            return entry["ltp"]
    return None


def _set_cached_ltp(strike_id: int, ltp: float, symbol: str = "") -> None:
    """Stores LTP in cache with current timestamp."""
    with _cache_lock:
        _ltp_cache[strike_id] = {
            "ltp":    ltp,
            "ts":     time.time(),
            "symbol": symbol,
            "time":   _ist_now(),
        }


def get_cache_snapshot() -> dict:
    """
    Returns copy of current LTP cache.
    Used by dashboard to show last-updated times.
    """
    with _cache_lock:
        return dict(_ltp_cache)


def invalidate_cache(strike_id: int = None) -> None:
    """
    Clears LTP cache.
    strike_id=None clears all; else clears specific strike.
    """
    with _cache_lock:
        if strike_id is None:
            _ltp_cache.clear()
            _log("LTP cache cleared (all strikes).", "CACHE")
        elif strike_id in _ltp_cache:
            del _ltp_cache[strike_id]
            _log(f"LTP cache cleared for strike {strike_id}.", "CACHE")


# ─────────────────────────────────────────────────────────────────────────────
# LTP FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ltp(strike: dict, force_refresh: bool = False) -> float:
    """
    Fetches current LTP for a single strike.

    Priority:
      1. Cache (if fresh and not force_refresh)
      2. Zerodha executor positions API
      3. Zerodha executor order book
      4. 0.0 fallback

    Paper mode: always returns 0.0.
    strike: dict from db.get_strike()

    Returns: LTP as float
    """
    strike_id    = strike["strike_id"]
    block        = db.get_block(strike["block_id"])
    expiry_date  = strike.get("expiry_date")
    if not expiry_date and block:
        expiry_date = block["expiry_date"]
    if not expiry_date:
        expiry_date = ""
    strike_price = strike["strike_price"]
    option_type  = strike["option_type"]

    # Build expected trading symbol for lookup
    exp_clean    = expiry_date.replace("-", "").upper()
    trading_sym  = f"NIFTY{exp_clean}{strike_price}{option_type}"

    # Paper mode check removed

    # Cache hit
    if not force_refresh:
        cached = _get_cached_ltp(strike_id)
        if cached is not None:
            return cached

    # Fetch from executor (resolve token dynamically since token is not stored in DB)
    token = ""
    try:
        resolved = kite_executor.search_option_symbol(
            expiry_date  = expiry_date,
            strike_price = int(strike_price),
            option_type  = option_type,
        )
        if resolved:
            token = resolved.get("token", "")
            trading_sym = resolved.get("trading_symbol", trading_sym)
    except Exception as e:
        _log(f"Error resolving symbol for strike {strike_id}: {e}", "WARN")

    ltp = kite_executor.get_ltp(
        symbol_token   = token,
        trading_symbol = trading_sym,
    )

    if ltp > 0:
        _set_cached_ltp(strike_id, ltp, trading_sym)
        return ltp

    # Fallback: return last cached value even if stale
    with _cache_lock:
        entry = _ltp_cache.get(strike_id)
        if entry:
            _log(f"Using stale cache for strike {strike_id} ({trading_sym}): LTP={entry['ltp']}", "WARN")
            return entry["ltp"]

    return 0.0


def fetch_all_ltps(block_id: int = None, force_refresh: bool = False) -> dict:
    """
    Fetches LTP for all OPEN and PENDING strikes.
    block_id=None fetches for all active blocks.

    Returns: {strike_id: ltp_float}
    """
    # Paper mode check removed

    if block_id is not None:
        all_s = db.get_strikes_by_block(block_id)
        strikes = [s for s in all_s if s["status"] in ("OPEN", "PENDING", "PENDING_CLOSE")]
    else:
        # All active blocks
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        strikes       = []
        for b in active_blocks:
            all_s = db.get_strikes_by_block(b["block_id"])
            strikes.extend([s for s in all_s if s["status"] in ("OPEN", "PENDING", "PENDING_CLOSE")])

    ltp_map = {}
    for s in strikes:
        ltp = fetch_ltp(s, force_refresh=force_refresh)
        ltp_map[s["strike_id"]] = ltp

    _log(f"LTP fetched for {len(ltp_map)} open/pending strike(s).", "LTP")
    return ltp_map


# ─────────────────────────────────────────────────────────────────────────────
# P&L CALCULATION (exact Blueprint formulas)
# ─────────────────────────────────────────────────────────────────────────────

def calc_strike_pnl(strike: dict, ltp: float) -> dict:
    """
    Calculates P&L for a single strike using Blueprint formulas.
    Includes both realized P&L from closed legs and unrealized P&L from the current open leg.

    Returns dict:
    {
      "strike_id"   : int,
      "strike_price": int,
      "option_type" : str,    # CE / PE
      "leg_type"    : str,    # SELL / HEDGE_BUY
      "status"      : str,    # OPEN / CLOSED / PENDING
      "anchor_price": float,
      "ltp"         : float,
      "lots"        : int,
      "lot_size"    : int,
      "pnl"         : float,  # Total P&L (realized + unrealized) in Rs
      "unrealized_pnl": float,
      "realized_pnl": float,
      "pnl_pct"     : float,  # P&L as % of entry/anchor
      "ltp_available": bool,  # False if LTP=0 (paper/no data)
    }
    """
    lot_size    = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    anchor      = float(strike.get("anchor_price", 0.0))
    lots        = int(strike.get("lots", 1))
    leg_type    = strike.get("leg_type", "SELL").upper()
    status      = strike.get("status", "PENDING").upper()
    
    # 1. Fetch all legs to sum realized P&L
    legs = db.get_legs_by_strike(strike["strike_id"])
    realized_pnl = sum(float(l["realized_pnl"] or 0.0) for l in legs if l.get("exit_time"))
    
    # Find actual entry price of the last leg
    eff_entry_price = anchor
    if legs:
        last_leg = sorted(legs, key=lambda x: x["leg_id"])[-1]
        eff_entry_price = float(last_leg["entry_price"])
    
    # 2. Compute unrealized P&L for the open leg
    unrealized_pnl = 0.0
    ltp_avail   = ltp > 0
    
    if status == "OPEN":
        # Find active open leg (where exit_time is empty/null)
        open_leg = None
        for l in legs:
            if not l.get("exit_time"):
                open_leg = l
                break
        
        entry_price = float(open_leg["entry_price"]) if open_leg else anchor
        
        if ltp_avail:
            if leg_type == "SELL":
                unrealized_pnl = (entry_price - ltp) * lots * lot_size
            elif leg_type == "HEDGE_BUY":
                unrealized_pnl = (ltp - entry_price) * lots * lot_size
    
    total_pnl = realized_pnl + unrealized_pnl

    # Calculate P&L as % basis
    pnl_pct = 0.0
    if status == "OPEN":
        entry_price = anchor
        for l in legs:
            if not l.get("exit_time"):
                entry_price = float(l["entry_price"])
                break
        if entry_price > 0 and ltp_avail:
            if leg_type == "SELL":
                pnl_pct = ((entry_price - ltp) / entry_price) * 100
            else:
                pnl_pct = ((ltp - entry_price) / entry_price) * 100
    elif status == "CLOSED" and anchor > 0:
        pnl_pct = (realized_pnl / (anchor * lots * lot_size)) * 100

    # For CLOSED strikes: find actual exit_price from the last closed leg
    exit_price = 0.0
    if status == "CLOSED":
        for l in legs:
            if l.get("exit_time") and float(l.get("exit_price") or 0.0) > 0:
                exit_price = float(l["exit_price"])
                break  # take the most recent closed leg

    # ltp shown in dashboard:
    #   OPEN or PENDING → live LTP from Zerodha API
    #   CLOSED          → actual exit_price (what we sold/bought at close)
    display_ltp = ltp if status in ("OPEN", "PENDING", "PENDING_CLOSE") else exit_price
    is_exit_price = (status == "CLOSED")

    return {
        "strike_id"    : strike["strike_id"],
        "block_id"     : strike.get("block_id"),
        "strike_price" : strike["strike_price"],
        "option_type"  : strike["option_type"],
        "leg_type"     : strike["leg_type"],
        "status"       : status,
        "anchor_price" : anchor,
        "entry_price"  : eff_entry_price,
        "ltp"          : display_ltp,
        "is_exit_price": is_exit_price,        # True = ltp column shows exit price
        "lots"         : lots,
        "lot_size"     : lot_size,
        "qty"          : lots * lot_size,
        "pnl"          : round(total_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "pnl_pct"      : round(pnl_pct, 2),
        "ltp_available": ltp_avail if status in ("OPEN", "PENDING", "PENDING_CLOSE") else (exit_price > 0),
        "hedge_strike_id": strike.get("hedge_strike_id"),
        "expiry_date"  : strike.get("expiry_date"),
    }


def calc_block_pnl(block_id: int, ltp_map: dict = None) -> dict:
    """
    Calculates total P&L for a block.

    If ltp_map is None, fetches LTPs automatically.
    ltp_map: {strike_id: ltp_float}

    Returns dict:
    {
      "block_id"    : int,
      "block_number": int,
      "expiry_date" : str,
      "expiry_type" : str,
      "status"      : str,
      "total_pnl"   : float,
      "open_strikes": int,
      "strike_pnls" : [calc_strike_pnl results for OPEN strikes],
      "last_updated": str,  # IST timestamp
    }
    """
    block = db.get_block(block_id)
    if not block:
        return {
            "ok": False,
            "message": f"Block {block_id} not found.",
        }

    # Fetch all strikes for the block (PENDING, OPEN, CLOSED)
    all_strikes = db.get_strikes_by_block(block_id)

    # Auto-fetch LTPs only for OPEN/PENDING strikes if not provided
    if ltp_map is None:
        ltp_map = {}
        for s in all_strikes:
            if s["status"] in ("OPEN", "PENDING", "PENDING_CLOSE"):
                ltp_map[s["strike_id"]] = fetch_ltp(s)

    total_pnl    = 0.0
    strike_pnls  = []

    for s in all_strikes:
        ltp  = ltp_map.get(s["strike_id"], 0.0)
        spnl = calc_strike_pnl(s, ltp)
        total_pnl   += spnl["pnl"]
        strike_pnls.append(spnl)

    return {
        "ok":           True,
        "block":        block,
        "block_id":     block_id,
        "block_number": block["block_number"],
        "expiry_date":  block["expiry_date"],
        "expiry_type":  block["expiry_type"],
        "status":       block["status"],
        "total_pnl":    round(total_pnl, 2),
        "open_strikes": len([s for s in all_strikes if s["status"] in ("OPEN", "PENDING_CLOSE")]),
        "strike_pnls":  strike_pnls,
        "last_updated": _ist_now(),
    }


def calc_portfolio_pnl(ltp_map: dict = None) -> dict:
    """
    Calculates total portfolio P&L across ALL active blocks.

    If ltp_map is None, fetches all LTPs automatically.

    Returns dict:
    {
      "total_pnl"     : float,   # Grand total across all blocks
      "active_blocks" : int,
      "total_open_strikes": int,
      "block_pnls"    : [calc_block_pnl results],
      "last_updated"  : str,
      "paper_mode"    : bool,
    }
    """
    # Fetch all LTPs at once if not provided
    if ltp_map is None:
        ltp_map = fetch_all_ltps()

    active_blocks       = db.get_all_blocks(status_filter="ACTIVE")
    total_pnl           = 0.0
    total_open_strikes  = 0
    block_pnls          = []

    for b in active_blocks:
        bpnl = calc_block_pnl(b["block_id"], ltp_map)
        if bpnl.get("ok"):
            total_pnl          += bpnl["total_pnl"]
            total_open_strikes += bpnl["open_strikes"]
            block_pnls.append(bpnl)

    return {
        "total_pnl"          : round(total_pnl, 2),
        "active_blocks"      : len(active_blocks),
        "total_open_strikes" : total_open_strikes,
        "block_pnls"         : block_pnls,
        "last_updated"       : _ist_now(),
        "paper_mode"         : False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTED DISPLAY HELPERS (for dashboard + telegram)
# ─────────────────────────────────────────────────────────────────────────────

def format_pnl(pnl: float, ltp_available: bool = True) -> str:
    """
    Formats P&L for display.
    Returns "--" if LTP not available (paper mode / no data).
    Returns "+Rs1,234.00" or "-Rs1,234.00"
    """
    if not ltp_available:
        return "--"
    if pnl >= 0:
        return f"+Rs{pnl:,.2f}"
    else:
        return f"-Rs{abs(pnl):,.2f}"


def format_pnl_pct(pct: float, ltp_available: bool = True) -> str:
    """Formats P&L percentage for display."""
    if not ltp_available:
        return "--"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def get_strike_display_row(s_pnl: dict) -> dict:
    """
    Returns a formatted row for dashboard table display.
    Ready for Streamlit dataframe.
    """
    ltp_avail  = s_pnl["ltp_available"]
    pnl        = s_pnl["pnl"]
    anchor     = s_pnl["anchor_price"]
    ltp        = s_pnl["ltp"]
    leg_type   = s_pnl["leg_type"]

    status     = s_pnl["status"]
    display_anchor = s_pnl["entry_price"]
    if leg_type == "HEDGE_BUY" and status == "PENDING":
        anchor_str = "--"
    else:
        anchor_str = f"Rs{display_anchor:.2f}"

    # Decay for sell legs: how much premium has decayed
    if leg_type == "SELL" and anchor > 0 and ltp_avail:
        decay_pct = ((anchor - ltp) / anchor) * 100
    else:
        decay_pct = 0.0

    return {
        "Strike"    : s_pnl["strike_price"],
        "Type"      : s_pnl["option_type"],
        "Leg"       : leg_type,
        "Anchor Rs" : anchor_str,
        "LTP Rs"    : f"Rs{ltp:.2f}" if ltp_avail else "--",
        "Lots"      : s_pnl["lots"],
        "Qty"       : s_pnl["qty"],
        "P&L Rs"    : format_pnl(pnl, ltp_avail),
        "P&L %"     : format_pnl_pct(s_pnl["pnl_pct"], ltp_avail),
        "Decay %"   : f"{decay_pct:.1f}%" if ltp_avail and leg_type == "SELL" else "--",
        "Status"    : s_pnl["status"],
    }


def get_block_display_summary(block_pnl: dict) -> dict:
    """
    Returns a formatted block summary for dashboard cards.
    """
    total        = block_pnl["total_pnl"]
    ltp_avail    = any(s["ltp_available"] for s in block_pnl["strike_pnls"])
    strike_rows  = [get_strike_display_row(s) for s in block_pnl["strike_pnls"]]

    return {
        "block_number" : block_pnl["block_number"],
        "expiry_date"  : block_pnl["expiry_date"],
        "expiry_type"  : block_pnl["expiry_type"],
        "status"       : block_pnl["status"],
        "open_strikes" : block_pnl["open_strikes"],
        "total_pnl"    : format_pnl(total, ltp_avail),
        "total_pnl_raw": total,
        "last_updated" : block_pnl["last_updated"],
        "strike_rows"  : strike_rows,
        "is_profitable": total >= 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM ALERT FORMATTERS (per Blueprint design)
# ─────────────────────────────────────────────────────────────────────────────

def build_block_daily_summary_msg(block_pnl: dict) -> str:
    """
    Builds Telegram daily block summary message per Blueprint format:

    BLOCK 1 DAILY SUMMARY
    Expiry: 26-Jun-2025 (Monthly)
    ━━━━━━━━━━━━━━━━━━━━
    24000 CE SELL:  +Rs4,250
    24000 PE SELL:  +Rs2,100
    24500 CE Hedge: -Rs1,200
    ━━━━━━━━━━━━━━━━━━━━
    Block P&L: +Rs5,150
    """
    lines = [
        f"BLOCK {block_pnl['block_number']} DAILY SUMMARY",
        f"Expiry: {block_pnl['expiry_date']} ({block_pnl['expiry_type'].title()})",
        "=" * 28,
    ]

    for s in block_pnl["strike_pnls"]:
        if s.get("status") == "PENDING":
            continue
        label = f"{s['strike_price']} {s['option_type']} {'SELL' if s['leg_type']=='SELL' else 'Hedge'}"
        pnl_str = format_pnl(s["pnl"], s["ltp_available"])
        lines.append(f"{label}: {pnl_str}")

    lines.append("=" * 28)
    total_str = format_pnl(block_pnl["total_pnl"], True)
    lines.append(f"Block P&L: {total_str}")
    return "\n".join(lines)


def build_portfolio_summary_msg(portfolio_pnl: dict) -> str:
    """
    Builds Telegram portfolio summary message.
    Shows each block P&L and grand total.
    """
    lines = [
        "ZERODHA OS -- PORTFOLIO SUMMARY",
        f"Time: {portfolio_pnl['last_updated']}",
        "=" * 35,
    ]

    for bp in portfolio_pnl["block_pnls"]:
        pnl_str = format_pnl(bp["total_pnl"], True)
        lines.append(
            f"Block {bp['block_number']} ({bp['expiry_date']}): {pnl_str}  [{bp['open_strikes']} open]"
        )

    lines.append("=" * 35)
    grand = format_pnl(portfolio_pnl["total_pnl"], True)
    lines.append(f"TOTAL PORTFOLIO P&L: {grand}")

    if portfolio_pnl.get("paper_mode"):
        lines.append("[PAPER MODE -- LTP not available]")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE CYCLE FUNCTION (called by main.py background loop)
# ─────────────────────────────────────────────────────────────────────────────

def run_pnl_cycle() -> dict:
    """
    Runs one full P&L update cycle.
    Fetches all LTPs, computes portfolio P&L, updates cache, returns results.
    Called by main.py every check_interval seconds.

    Returns: portfolio_pnl dict
    """
    global _last_exit_check_time, _last_exit_check_candle
    _log("Running P&L cycle...", "CYCLE")
    
    # Run broker positions synchronization
    try:
        import block_manager as bm
        bm.sync_positions_with_broker()
    except Exception as sync_err:
        _log(f"Error syncing positions: {sync_err}", "ERROR")

    start = time.time()

    portfolio = calc_portfolio_pnl()

    # ── Auto-Exit Stop Loss & Re-entry Checks ────────────────────────────────
    is_algo_running = db.get("algo_running", "ON") == "ON"
    if is_algo_running:
        try:
            import block_manager as bm
            import telegram_bot as tg
            
            blocks = db.get_all_blocks(status_filter="ACTIVE")
            now_ts = time.time()
            now_ist = datetime.now(IST)
            now_time_str = now_ist.strftime("%H:%M")
            today_str = now_ist.strftime("%Y-%m-%d")
            
            # Decoupled Stop-Loss Exit Check (Runs on 5-minute candle closed boundaries)
            run_exit_checks = False
            floor_min = (now_ist.minute // 5) * 5
            curr_5m_str = f"{today_str} {now_ist.hour:02d}:{floor_min:02d}"
            if _last_exit_check_candle != curr_5m_str:
                run_exit_checks = True
                _last_exit_check_candle = curr_5m_str
                _log(f"Running stop-loss exit checks for 5-minute candle boundary: {curr_5m_str}", "CYCLE")
            
            for b in blocks:
                # 1. Stop-Loss Exit Check (Only run on exit-check interval)
                if run_exit_checks:
                    strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
                    for s in strikes:
                        if s["leg_type"] == "SELL":
                            strike_id = s["strike_id"]
                            anchor_price = float(s["anchor_price"])
                            
                            ltp = fetch_ltp(s, force_refresh=True)
                            if ltp <= 0:
                                continue
                                
                            buffer_tolerance = float(db.get("buffer_tolerance", "2.0"))
                            exit_threshold = anchor_price + buffer_tolerance
                            
                            _log(f"[AUTO-EXIT-CHECK] Strike {s['strike_price']} {s['option_type']}: LTP={ltp:.2f} | Threshold={exit_threshold:.2f} (Anchor={anchor_price:.2f} + Buffer={buffer_tolerance:.2f})", "CYCLE")
                            
                            if ltp >= exit_threshold:
                                _log(f"[AUTO-EXIT] LTP {ltp:.2f} >= Threshold {exit_threshold:.2f} for Strike {s['strike_price']} {s['option_type']}. Triggering close...", "WARN")
                                
                                # close_hedge=False: Keep hedge OPEN for potential re-entry during market hours.
                                # The EOD Hedge Orphan Watchdog (below) will close it after 15:30 if unused.
                                res = bm.close_strike(strike_id, close_hedge=False)
                                block_num = b["block_number"]
                                
                                # Determine hedge status for the alert
                                hedge_id = s.get("hedge_strike_id")
                                hedge_info = db.get_strike(hedge_id) if hedge_id else None
                                hedge_status_msg = ""
                                if hedge_info and hedge_info["status"] == "OPEN":
                                    hedge_status_msg = (
                                        f"🛡️ Hedge ({hedge_info['strike_price']} {hedge_info['option_type']}): OPEN\n"
                                        f"   → Re-entry window active. Hedge will auto-close at 15:30 if not re-entered.\n"
                                        f"   → To close hedge now: use Dashboard → Close Hedge button."
                                    )
                                else:
                                    hedge_status_msg = "🛡️ Hedge: No linked hedge found."
                                
                                if res["ok"]:
                                    alert_msg = (
                                        f"🚨 <b>AUTO-EXIT TRIGGERED</b> 🚨\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} breached Anchor ₹{anchor_price:.2f} + Buffer ₹{buffer_tolerance:.2f}\n"
                                        f"✅ Sell leg CLOSED on broker.\n"
                                        f"{hedge_status_msg}"
                                    )
                                    tg.send(alert_msg)
                                else:
                                    alert_msg = (
                                        f"⚠️ <b>AUTO-EXIT FAILED</b> ⚠️\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} breached threshold ₹{exit_threshold:.2f}\n"
                                        f"Error: {res['message']}\n"
                                        f"<b>⚠️ Action required: Please close manually from Dashboard!</b>"
                                    )
                                    tg.send(alert_msg)
                                    
                # 2. Auto Re-Entry Check (Runs every cycle / every 30 seconds)
                # GUARD (Fix #2): Only consider re-entry for:
                #   a) Strikes closed TODAY (same trading day)
                #   b) Block has not yet expired
                #   c) We are still within market hours (before 15:15 IST)
                is_market_open_for_reentry = now_time_str < "15:15"
                if not is_market_open_for_reentry:
                    pass  # Skip re-entry after 15:15 — EOD watchdog handles hedge close below
                else:
                    closed_strikes = db.get_strikes_by_block(b["block_id"], status_filter="CLOSED")
                    for s in closed_strikes:
                        if s["leg_type"] == "SELL":
                            strike_id = s["strike_id"]
                            anchor_price = float(s["anchor_price"])
                            
                            # GUARD: Only re-enter if the sell was closed TODAY
                            legs = db.get_legs_by_strike(strike_id)
                            closed_today = False
                            for leg in legs:
                                exit_time = leg.get("exit_time", "")
                                if exit_time and exit_time.startswith(today_str):
                                    closed_today = True
                                    break
                            if not closed_today:
                                continue  # Strike was closed on a previous day — skip re-entry
                            
                            # GUARD: Limit same-day entries to prevent whipsaw losses (default: 10 entries per day max)
                            today_entries = sum(1 for leg in legs if leg.get("entry_time", "").startswith(today_str))
                            max_reentries = int(db.get("max_same_day_reentries", "10"))
                            if today_entries >= max_reentries:
                                _log(f"[RE-ENTRY-GUARD] Strike {s['strike_price']} {s['option_type']} blocked: already has {today_entries} entries today (max {max_reentries}).", "CYCLE")
                                continue
                            
                            # GUARD: Block must not be expired
                            block_expiry = b.get("expiry_date", "")
                            if block_expiry and today_str > block_expiry:
                                continue  # Block expired — skip re-entry
                            
                            # Verify that the linked hedge strike exists and is OPEN
                            hedge_id = s.get("hedge_strike_id")
                            if not hedge_id:
                                continue
                            
                            hedge_strike = db.get_strike(hedge_id)
                            if not hedge_strike or hedge_strike["status"] != "OPEN":
                                continue
                            
                            ltp = fetch_ltp(s, force_refresh=True)
                            if ltp <= 0:
                                continue
                                
                            _log(f"[RE-ENTRY-CHECK] Strike {s['strike_price']} {s['option_type']}: LTP={ltp:.2f} | Anchor={anchor_price:.2f}", "CYCLE")
                            
                            if ltp < anchor_price:
                                _log(f"[RE-ENTRY] LTP {ltp:.2f} < Anchor {anchor_price:.2f} for Strike {s['strike_price']} {s['option_type']}. Triggering re-entry...", "WARN")
                                
                                res = bm.execute_strike(strike_id)
                                block_num = b["block_number"]
                                
                                if res["ok"]:
                                    alert_msg = (
                                        f"🔄 <b>AUTO-RE-ENTRY TRIGGERED</b> 🔄\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} fell back below Anchor ₹{anchor_price:.2f}\n"
                                        f"✅ Re-entered SELL leg on broker (using existing open hedge)."
                                    )
                                    tg.send(alert_msg)
                                else:
                                    alert_msg = (
                                        f"⚠️ <b>AUTO-RE-ENTRY FAILED</b> ⚠️\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} fell back below Anchor ₹{anchor_price:.2f}\n"
                                        f"Error: {res['message']}\n"
                                        f"<b>⚠️ Action required: Please review from Dashboard!</b>"
                                    )
                                    tg.send(alert_msg)

                    # 2b. Auto-Entry for Pending Strikes (Runs every cycle / every 30 seconds)
                    # If a strike is PENDING, we auto-execute it if LTP < anchor_price.
                    pending_strikes = db.get_strikes_by_block(b["block_id"], status_filter="PENDING")
                    for s in pending_strikes:
                        if s["leg_type"] == "SELL":
                            strike_id = s["strike_id"]
                            anchor_price = float(s["anchor_price"])
                            
                            ltp = fetch_ltp(s, force_refresh=True)
                            if ltp <= 0:
                                continue
                                
                            _log(f"[PENDING-ENTRY-CHECK] Strike {s['strike_price']} {s['option_type']}: LTP={ltp:.2f} | Anchor={anchor_price:.2f}", "CYCLE")
                            
                            if ltp < anchor_price:
                                _log(f"[PENDING-ENTRY] LTP {ltp:.2f} < Anchor {anchor_price:.2f} for Strike {s['strike_price']} {s['option_type']}. Triggering entry...", "WARN")
                                
                                res = bm.execute_strike(strike_id)
                                block_num = b["block_number"]
                                
                                if res["ok"]:
                                    alert_msg = (
                                        f"🚀 <b>AUTO-ENTRY TRIGGERED</b> 🚀\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} fell below Anchor ₹{anchor_price:.2f}\n"
                                        f"✅ Executed new Hedge Buy & Sell leg on broker."
                                    )
                                    tg.send(alert_msg)
                                else:
                                    alert_msg = (
                                        f"⚠️ <b>AUTO-ENTRY FAILED</b> ⚠️\n"
                                        f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} SELL\n"
                                        f"Reason: LTP ₹{ltp:.2f} fell below Anchor ₹{anchor_price:.2f}\n"
                                        f"Error: {res['message']}\n"
                                        f"<b>⚠️ Action required: Please review from Dashboard!</b>"
                                    )
                                    tg.send(alert_msg)
            
            # ── 3. EOD Hedge Orphan Watchdog (Fix #1) ────────────────────────
            # After 15:15 IST, find any SELL strike that is CLOSED but its
            # linked hedge is still OPEN (orphaned hedge). Auto-schedule hedge
            # close via PENDING_CLOSE queue. This covers the case where:
            #   - Auto-exit fired with close_hedge=False (re-entry window)
            #   - Re-entry did NOT happen before market close
            #   - Hedge is now stranded open with no one to close it
            if now_time_str >= "15:15":
                _log("Running EOD hedge orphan watchdog...", "CYCLE")
                orphan_key_prefix = "eod_orphan_warned_"
                for b in blocks:
                    closed_sells = db.get_strikes_by_block(b["block_id"], status_filter="CLOSED")
                    for s in closed_sells:
                        if s["leg_type"] != "SELL":
                            continue
                        hedge_id = s.get("hedge_strike_id")
                        if not hedge_id:
                            continue
                        hedge = db.get_strike(hedge_id)
                        if not hedge or hedge["status"] != "OPEN":
                            continue
                        
                        # Found an orphaned open hedge — schedule it for immediate close
                        warn_key = f"{orphan_key_prefix}{hedge_id}_{today_str}"
                        already_warned = db.get(warn_key, "")
                        if already_warned:
                            continue  # Already queued today
                        
                        _log(
                            f"[EOD-WATCHDOG] Orphaned hedge found: Strike {hedge['strike_price']} "
                            f"{hedge['option_type']} HEDGE_BUY (id={hedge_id}) for closed SELL "
                            f"{s['strike_price']} {s['option_type']} (id={s['strike_id']}). "
                            f"Scheduling for immediate close.",
                            "WARN"
                        )
                        
                        # Schedule it via the standard PENDING_CLOSE queue
                        db.update_strike_status(hedge_id, "PENDING_CLOSE")
                        db.set(f"pending_close_time_{hedge_id}", str(time.time()))  # immediate
                        db.set(warn_key, "1")  # Mark as warned/queued for today
                        
                        tg.send(
                            f"🛡️ <b>EOD HEDGE ORPHAN DETECTED & QUEUED</b>\n"
                            f"Block {b['block_number']} | Hedge {hedge['strike_price']} "
                            f"{hedge['option_type']} HEDGE_BUY\n"
                            f"Sell leg {s['strike_price']} {s['option_type']} was closed earlier today.\n"
                            f"Re-entry window expired (after 15:15). Scheduling hedge close now.\n"
                            f"⏳ Background engine will execute hedge exit shortly."
                        )
        except Exception as ae_err:
            _log(f"Error in P&L cycle auto-exit/watchdog: {ae_err}", "ERROR")

    elapsed = time.time() - start
    _log(
        f"P&L cycle complete in {elapsed:.2f}s | "
        f"Total P&L: {format_pnl(portfolio['total_pnl'])} | "
        f"Active blocks: {portfolio['active_blocks']} | "
        f"Open strikes: {portfolio['total_open_strikes']}",
        "CYCLE"
    )

    # Update last cycle time
    db.set("last_cycle_time", _ist_now())

    return portfolio


# Paper mode simulation removed
