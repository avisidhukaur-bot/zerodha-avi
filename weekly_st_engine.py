"""
weekly_st_engine.py -- Weekly SuperTrend (8,2) 2-Hour Autonomous Option Selling Engine
======================================================================================
System: Bharat Systems — Zerodha OS Extension
Architecture: W-Unit (W1) Autonomous Spread Engine
Version: V1.0 Base Lego Architecture (Production Edition)

CORE SPECIFICATION:
  1. Indicator: SuperTrend (Period=8, Multiplier=3.0) on 2-Hour Resampled Nifty Spot Candles.
  2. Execution Pulses: Exactly 3 times a day:
       - Pulse 1: 11:15 AM IST (09:15 - 11:15 2H candle close & Monday First-Signal Rollover)
       - Pulse 2: 01:15 PM IST (11:15 - 13:15 2H candle close)
       - Pulse 3: 03:10 PM IST (13:15 - 15:10 afternoon wrap)
  3. Product & Hunter:
       - Weekly Option Spreads
       - Bullish (Spot > ST) -> Bull Put Spread: Sell OTM Put @ Rs80-100, Buy Put Hedge @ -500 pts.
       - Bearish (Spot < ST) -> Bear Call Spread: Sell OTM Call @ Rs80-100, Buy Call Hedge @ +500 pts.
       - Fallback: If Rs80-Rs100 not found in current weekly expiry, auto-shift to Next Week Expiry.
  4. Execution Safety Invariant:
       - Entry: Buy Hedge First -> Sell Short Leg Second (margin relief & zero naked margin hit).
       - Exit / Square-off: Buy to close Short Leg First -> Sell to close Hedge Leg Second.
  5. Monday Rollover: Executes on the FIRST SIGNAL of Monday (Pulse 1 @ 11:15 AM) to roll Tuesday weekly contracts to next week.
  6. Emergency Kill Switch: 1-click immediate market close of all open W-unit legs.
  7. Lot Size: Configurable variable (defaults to 1 lot for initial verification).
"""

import os
import sys
import time
import sqlite3
import threading
from datetime import datetime, date, time as dt_time, timedelta
from typing import Optional, Dict, Any, List, Tuple
import pytz
import pandas as pd
import numpy as np
import streamlit as st

import db
import config as cfg
import utils
from kite_executor import kite_executor
import telegram_bot as tg

IST = pytz.timezone("Asia/Kolkata")
NIFTY_TOKEN = 256265  # NSE:NIFTY 50

# Thread-safe lock for W-Unit DB actions
_w_lock = threading.Lock()


def _log(msg: str, tag: str = "W_ST") -> None:
    """Standardized logger for Weekly ST Engine."""
    utils.log(f"[{tag}] {msg}", tag)


def _ist_now() -> str:
    """Current IST datetime string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE TABLE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def init_weekly_st_db():
    """Initializes the isolated weekly_st_positions table in SQLite."""
    with _w_lock:
        conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_st_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_name TEXT DEFAULT 'W1',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                lots INTEGER DEFAULT 1,
                
                sell_strike INTEGER NOT NULL,
                sell_option_type TEXT NOT NULL,
                sell_entry_price REAL DEFAULT 0.0,
                sell_exit_price REAL DEFAULT 0.0,
                sell_symbol TEXT NOT NULL,
                sell_token INTEGER DEFAULT 0,
                
                hedge_strike INTEGER NOT NULL,
                hedge_option_type TEXT NOT NULL,
                hedge_entry_price REAL DEFAULT 0.0,
                hedge_exit_price REAL DEFAULT 0.0,
                hedge_symbol TEXT NOT NULL,
                hedge_token INTEGER DEFAULT 0,
                
                realized_pnl REAL DEFAULT 0.0,
                exit_reason TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()


# Ensure table exists on module load
try:
    init_weekly_st_db()
except Exception as e:
    _log(f"DB Init warning: {e}", "WARN")


# ─────────────────────────────────────────────────────────────────────────────
# 2-HOUR NATIVE CANDLES & DYNAMIC SUPERTREND (8, 2) (ZERODHA PARITY)
# ─────────────────────────────────────────────────────────────────────────────

_candles_cache = {"timestamp": 0.0, "df": None}


def fetch_2h_candles(lookback_days: int = 120, force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches official native 2-Hour candles directly from Zerodha Kite Connect API (interval='2hour').
    Uses 120-day lookback (300+ candles) to ensure 100% exact convergence with Zerodha Kite Charts.
    Caches historical candles for 60 seconds to prevent rate-limiting while dynamically
    updating the latest candle with real-time NIFTY Spot LTP.
    """
    global _candles_cache
    now_ts = time.time()
    df = None

    # 1. Use cached historical df if within 60s
    if not force_refresh and _candles_cache["df"] is not None and (now_ts - _candles_cache["timestamp"] < 60.0):
        df = _candles_cache["df"].copy()
    else:
        # Fetch from Zerodha Kite API (native '2hour' interval)
        if kite_executor.ensure_logged_in() and kite_executor.kite:
            try:
                to_date = datetime.now(IST)
                from_date = to_date - timedelta(days=lookback_days)
                records = kite_executor.kite.historical_data(
                    instrument_token=NIFTY_TOKEN,
                    from_date=from_date.strftime("%Y-%m-%d"),
                    to_date=to_date.strftime("%Y-%m-%d"),
                    interval="2hour"
                )
                if records:
                    df = pd.DataFrame(records)
                    df.rename(columns={"date": "Datetime", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
                    df["Datetime"] = pd.to_datetime(df["Datetime"])
                    _candles_cache["df"] = df.copy()
                    _candles_cache["timestamp"] = now_ts
            except Exception as e:
                _log(f"Kite native 2hour fetch error: {e}", "WARN")

        # Fallback to yfinance if Kite was unavailable
        if df is None or df.empty:
            try:
                import yfinance as yf
                raw_yf = yf.download("^NSEI", period="60d", interval="15m", progress=False)
                if isinstance(raw_yf.columns, pd.MultiIndex):
                    raw_yf.columns = raw_yf.columns.get_level_values(0)
                raw_yf = raw_yf.dropna()
                if not raw_yf.empty:
                    df_yf = raw_yf.reset_index()
                    date_col = "Datetime" if "Datetime" in df_yf.columns else "Date"
                    df_yf.rename(columns={date_col: "Datetime"}, inplace=True)
                    df = df_yf.set_index("Datetime").resample("2h", offset="15m").agg({
                        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                    }).dropna().reset_index()
            except Exception as e:
                _log(f"yfinance fallback failed: {e}", "ERROR")

    if df is None or df.empty:
        _log("Could not obtain intraday candles for SuperTrend calculation.", "ERROR")
        return pd.DataFrame()

    # Dynamic Real-time Spot injection into current in-progress candle
    live_spot = kite_executor.get_nifty_spot()
    if live_spot and live_spot > 0:
        last_idx = df.index[-1]
        df.loc[last_idx, "Close"] = live_spot
        if live_spot > df.loc[last_idx, "High"]:
            df.loc[last_idx, "High"] = live_spot
        if live_spot < df.loc[last_idx, "Low"]:
            df.loc[last_idx, "Low"] = live_spot

    return df


def calculate_supertrend_2h(period: int = 8, multiplier: float = 2.0, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Computes SuperTrend (8, 2) on official native 2-Hour Zerodha Kite candles.
    Uses Wilder's RMA (alpha = 1/period) matching ChartIQ/TradingView on Zerodha Kite.
    Returns real-time dynamic spot, supertrend value, distance, and regime.
    """
    df = fetch_2h_candles(lookback_days=120, force_refresh=force_refresh)
    if df.empty or len(df) < (period + 2):
        spot = kite_executor.get_nifty_spot() or 22800.0
        return {
            "ok": False,
            "spot": spot,
            "supertrend": spot,
            "regime": "NEUTRAL",
            "trend_val": 0,
            "distance": 0.0,
            "distance_pct": 0.0,
            "atr": 0.0,
            "last_candle_date": "--",
            "last_slot": 0,
            "df": df
        }

    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    # 1. True Range calculation
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    # 2. ATR using Wilder's RMA (alpha = 1 / period)
    atr = pd.Series(tr).ewm(alpha=1.0 / period, adjust=False).mean().values

    hl2 = (high + low) / 2.0
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = np.zeros(n)

    for i in range(n):
        if i == 0:
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            trend[i] = 1 if close[i] >= hl2[i] else -1
            supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]
            continue

        # Final Upper Band logic
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final Lower Band logic
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Trend Flip & SuperTrend Assignment
        if trend[i - 1] == 1:
            if close[i] < final_lower[i]:
                trend[i] = -1
                supertrend[i] = final_upper[i]
            else:
                trend[i] = 1
                supertrend[i] = final_lower[i]
        else:
            if close[i] > final_upper[i]:
                trend[i] = 1
                supertrend[i] = final_lower[i]
            else:
                trend[i] = -1
                supertrend[i] = final_upper[i]

    df["SuperTrend"] = supertrend
    df["Trend"] = trend
    df["Regime"] = np.where(trend == 1, "BULLISH", "BEARISH")

    latest = df.iloc[-1]
    live_spot = kite_executor.get_nifty_spot()
    spot = live_spot if (live_spot and live_spot > 0) else float(latest["Close"])
    st_val = float(latest["SuperTrend"])
    atr_val = float(atr[-1])

    regime = "BULLISH" if spot >= st_val else "BEARISH"
    trend_val = 1 if regime == "BULLISH" else -1
    dist = spot - st_val
    dist_pct = (dist / spot) * 100.0 if spot > 0 else 0.0

    return {
        "ok": True,
        "spot": round(spot, 2),
        "supertrend": round(st_val, 2),
        "atr": round(atr_val, 2),
        "regime": regime,
        "trend_val": trend_val,
        "distance": round(dist, 2),
        "distance_pct": round(dist_pct, 2),
        "last_candle_date": str(latest.get("Datetime", "--")),
        "last_slot": len(df),
        "df": df
    }


# ─────────────────────────────────────────────────────────────────────────────
# SMART STRIKE HUNTER & NEXT-WEEK FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

def get_upcoming_weekly_expiries() -> List[str]:
    """Retrieves upcoming valid weekly option expiries sorted chronologically."""
    try:
        df = kite_executor._load_security_master()
        if df.empty:
            return []
        nifty_opts = df[(df["name"] == "NIFTY") & (df["exchange"] == "NFO") & (df["instrument_type"].isin(["CE", "PE"]))]
        expiries = sorted(nifty_opts["expiry"].dropna().unique())
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        valid = [str(exp) for exp in expiries if str(exp) >= today_str]
        return valid
    except Exception as e:
        _log(f"Error fetching expiries: {e}", "ERROR")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION & STRATEGY PERSISTENCE (DECIDE & LOCK)
# ─────────────────────────────────────────────────────────────────────────────

def get_weekly_st_settings() -> Dict[str, Any]:
    """Retrieves Weekly ST strategy configuration, lock status, and safety thresholds."""
    return {
        "locked": db.get("weekly_st_expiry_locked", "0") == "1",
        "locked_at": db.get("weekly_st_expiry_locked_at", ""),
        "expiry_mode": db.get("weekly_st_expiry_mode", "AUTO"),
        "target_expiry": db.get("weekly_st_target_expiry", ""),
        "min_spot_buffer": float(db.get("weekly_st_min_spot_buffer", "150.0") or 150.0),
        "st_clearance": float(db.get("weekly_st_st_clearance", "50.0") or 50.0),
        "lots": int(db.get("weekly_st_lots", "1") or 1),
        "min_prem": float(db.get("weekly_st_target_prem_min", "80.0") or 80.0),
        "max_prem": float(db.get("weekly_st_target_prem_max", "100.0") or 100.0),
        "hedge_dist": int(db.get("weekly_st_hedge_dist", "500") or 500)
    }


def set_weekly_st_settings(
    locked: bool,
    expiry_mode: str,
    target_expiry: str = "",
    min_spot_buffer: float = 150.0,
    st_clearance: float = 50.0
) -> None:
    """Saves and locks/unlocks the Weekly ST strategy configuration in DB."""
    db.set("weekly_st_expiry_locked", "1" if locked else "0")
    if locked:
        db.set("weekly_st_expiry_locked_at", _ist_now())
    db.set("weekly_st_expiry_mode", str(expiry_mode).strip())
    db.set("weekly_st_target_expiry", str(target_expiry).strip())
    db.set("weekly_st_min_spot_buffer", str(min_spot_buffer))
    db.set("weekly_st_st_clearance", str(st_clearance))


# ─────────────────────────────────────────────────────────────────────────────
# FORTIFIED STRIKE HUNTER WITH SUPERTREND MOAT & NEXT-WEEK FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

def hunt_weekly_st_spread(
    direction: str,
    min_prem: float = 80.0,
    max_prem: float = 100.0,
    hedge_distance: int = 500,
    force_next_week: bool = False,
    expiry_mode: Optional[str] = None,
    target_expiry: Optional[str] = None,
    min_spot_buffer: Optional[float] = None,
    st_clearance: Optional[float] = None,
    st_value: Optional[float] = None,
    spot_val: Optional[float] = None
) -> Dict[str, Any]:
    """
    Fortified Automated Strike Hunter with SuperTrend Moat & Operator Expiry Selection:
      1. Determines required option wing:
         - BULLISH -> Bull Put Spread (Sell OTM PE, Buy PE Hedge @ -500 pts)
         - BEARISH -> Bear Call Spread (Sell OTM CE, Buy CE Hedge @ +500 pts)
      2. Enforces Operator Expiry Mode:
         - 'AUTO' (Safety First): Scans Current Week; auto-shifts to Next Week if SuperTrend moat/spot buffer is breached or decayed out.
         - 'FORCE_NEXT': Skips current week entirely; strictly trades Next Week.
         - 'FORCE_CURRENT': Trades current week only, strictly respecting safety moat (fails safely if unsafe).
         - 'MANUAL': Trades the operator-selected target expiry date.
      3. Mathematical SuperTrend Moat & Spot Clearance:
         - BULLISH PE: strike <= (spot - min_spot_buffer) AND strike <= (ST - st_clearance)
         - BEARISH CE: strike >= (spot + min_spot_buffer) AND strike >= (ST + st_clearance)
      4. Fallback Trigger: Auto-elevates to Next Week if Current Week has no safe strike >= Rs65.
      5. Maps protective Hedge Armor strike (+/- 500 points).
    """
    expiries = get_upcoming_weekly_expiries()
    if not expiries:
        return {"ok": False, "message": "No valid weekly expiries found in security master."}

    # Fetch configuration defaults if not passed explicitly
    cfg_st = get_weekly_st_settings()
    eff_mode = (expiry_mode or cfg_st["expiry_mode"] or "AUTO").strip().upper()
    if force_next_week:
        eff_mode = "FORCE_NEXT"

    buf_spot = float(min_spot_buffer if min_spot_buffer is not None else cfg_st["min_spot_buffer"])
    buf_st = float(st_clearance if st_clearance is not None else cfg_st["st_clearance"])
    eff_target_exp = str(target_expiry or cfg_st["target_expiry"] or "").strip()

    # Resolve Spot and SuperTrend
    live_spot = spot_val if (spot_val and spot_val > 0) else kite_executor.get_nifty_spot()
    st_val = float(st_value) if (st_value is not None and st_value > 0) else 0.0

    if not live_spot or live_spot <= 0 or st_val <= 0:
        st_res = calculate_supertrend_2h(period=8, multiplier=2.0)
        if not live_spot or live_spot <= 0:
            live_spot = float(st_res.get("spot", 22800.0) or 22800.0)
        if st_val <= 0:
            st_val = float(st_res.get("supertrend", 0.0) or 0.0)

    spot = live_spot or 22800.0
    option_type = "PE" if direction.upper() == "BULLISH" else "CE"
    target_mid = (min_prem + max_prem) / 2.0  # ideal ~90.0

    current_exp = expiries[0]
    next_exp = expiries[1] if len(expiries) > 1 else current_exp

    now_dt = datetime.now(IST)
    is_monday = (now_dt.weekday() == 0)

    # Determine primary starting expiry and fallback allowance
    if "NEXT" in eff_mode:
        primary_exp = next_exp
        allow_fallback = False
        mode_label = "FORCE_NEXT"
    elif "CURRENT" in eff_mode:
        primary_exp = current_exp
        allow_fallback = False
        mode_label = "FORCE_CURRENT"
    elif "MANUAL" in eff_mode and eff_target_exp in expiries:
        primary_exp = eff_target_exp
        allow_fallback = False
        mode_label = f"MANUAL ({eff_target_exp})"
    else:  # AUTO
        mode_label = "AUTO (SAFETY FIRST)"
        if is_monday:
            primary_exp = next_exp
            allow_fallback = False
        else:
            primary_exp = current_exp
            allow_fallback = (next_exp != current_exp)

    def _scan_expiry(expiry_to_scan: str, enforce_st_moat: bool = True) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        # Compute exact safe strike boundaries according to SuperTrend Moat & Spot Buffer
        if option_type == "PE":
            # Put Selling: Short strike must sit BELOW Spot. If enforce_st_moat is True, also BELOW SuperTrend
            max_by_spot = spot - buf_spot
            if enforce_st_moat and st_val > 0:
                max_allowed = min(max_by_spot, st_val - buf_st)
                rule_desc = f"<= {max_allowed:.0f} PE (Moat: ST {st_val:.1f} & Spot {spot:.1f})"
            else:
                max_allowed = max_by_spot
                rule_desc = f"<= {max_allowed:.0f} PE (Natural Theta: Spot {spot:.1f} - Buffer {buf_spot}pt)"

            base_50 = int(round(max_allowed / 50.0) * 50)
            if base_50 > max_allowed:
                base_50 -= 50
            strike_range = range(base_50, base_50 - 1600, -50)
            moat_info = {"bound": max_allowed, "base": base_50, "rule": rule_desc}
        else:
            # Call Selling: Short strike must sit ABOVE Spot. If enforce_st_moat is True, also ABOVE SuperTrend
            min_by_spot = spot + buf_spot
            if enforce_st_moat and st_val > 0:
                min_allowed = max(min_by_spot, st_val + buf_st)
                rule_desc = f">= {min_allowed:.0f} CE (Moat: ST {st_val:.1f} & Spot {spot:.1f})"
            else:
                min_allowed = min_by_spot
                rule_desc = f">= {min_allowed:.0f} CE (Natural Theta: Spot {spot:.1f} + Buffer {buf_spot}pt)"

            base_50 = int(round(min_allowed / 50.0) * 50)
            if base_50 < min_allowed:
                base_50 += 50
            strike_range = range(base_50, base_50 + 1600, 50)
            moat_info = {"bound": min_allowed, "base": base_50, "rule": rule_desc}

        sym_map = {}
        for sp in strike_range:
            sym_info = kite_executor.search_option_symbol(expiry_to_scan, sp, option_type)
            if sym_info:
                sym_map[sp] = sym_info

        if not sym_map:
            return None, moat_info

        # ── High-speed Batch Quote ──
        ltp_map = {}
        if kite_executor.ensure_logged_in() and kite_executor.kite:
            try:
                queries = [f"NFO:{s['trading_symbol']}" for s in sym_map.values()]
                q_res = kite_executor.kite.quote(queries)
                for q_key, q_data in q_res.items():
                    tsym = q_key.replace("NFO:", "")
                    ltp_map[tsym] = float(q_data.get("last_price", 0.0) or 0.0)
            except Exception as e:
                _log(f"Batch quote failed, falling back to individual: {e}", "WARN")

        candidates = []
        for sp, sym_info in sym_map.items():
            tsym = sym_info["trading_symbol"]
            ltp = ltp_map.get(tsym)
            if ltp is None or ltp == 0:
                ltp = kite_executor.get_ltp(sym_info["token"], tsym)
            if ltp > 0:
                candidates.append({
                    "strike": sp,
                    "sym_info": sym_info,
                    "ltp": ltp,
                    "diff": abs(ltp - target_mid),
                    "in_range": (min_prem <= ltp <= max_prem)
                })

        if not candidates:
            return None, moat_info

        # Filter strictly in range first
        in_range = [c for c in candidates if c["in_range"]]
        if in_range:
            in_range.sort(key=lambda x: x["diff"])
            return in_range[0], moat_info

        # If none strictly in range, check if top candidate is at least near floor (Rs65)
        candidates.sort(key=lambda x: x["diff"])
        best = candidates[0]
        if best["ltp"] >= 65.0:
            return best, moat_info

        return None, moat_info

    # ── STEP 1: SCAN PRIMARY TARGET EXPIRY (Strict SuperTrend Moat) ──
    is_fallback = False
    fallback_reason = ""
    chosen_expiry = primary_exp

    best_sell, moat_meta = _scan_expiry(primary_exp, enforce_st_moat=True)

    # ── STEP 2: FALLBACK TO NEXT WEEK (Natural Alpha / Theta, ST Moat Bypassed) ──
    if not best_sell:
        if allow_fallback and next_exp != primary_exp:
            _log(f"Current week {primary_exp} safe strikes decayed (<Rs65). Auto-shifting to Next Week {next_exp} (Natural Theta Line)...", "FALLBACK")
            best_sell_next, moat_meta_next = _scan_expiry(next_exp, enforce_st_moat=False)
            if best_sell_next:
                best_sell = best_sell_next
                chosen_expiry = next_exp
                is_fallback = True
                moat_meta = moat_meta_next
                fallback_reason = f"Current week {primary_exp} decayed (<Rs65); auto-shifted to Next Week {next_exp} (Natural Theta: {moat_meta['rule']})"
            elif len(expiries) > 2 and expiries[2] not in (primary_exp, next_exp):
                # ── STEP 2b: DEEP VOLATILITY CASCADE TO MONTHLY EXPIRY ──
                monthly_exp = expiries[2]
                _log(f"Next week {next_exp} safe strikes also decayed (<Rs65). Cascading to Monthly Expiry {monthly_exp}...", "CASCADE")
                best_sell_mon, moat_meta_mon = _scan_expiry(monthly_exp, enforce_st_moat=False)
                if best_sell_mon:
                    best_sell = best_sell_mon
                    chosen_expiry = monthly_exp
                    is_fallback = True
                    moat_meta = moat_meta_mon
                    fallback_reason = f"Current & Next week decayed (<Rs65); cascaded to Monthly {monthly_exp} (Natural Theta: {moat_meta['rule']})"
        else:
            return {
                "ok": False,
                "message": f"SAFETY MOAT ENFORCED: No safe strike in {primary_exp} meets Rs{min_prem}-Rs{max_prem} outside SuperTrend moat ({moat_meta['rule']}). Mode '{mode_label}' prevents shifting."
            }

    if not best_sell:
        return {
            "ok": False,
            "message": f"Could not find liquid {option_type} strike near Rs{min_prem}-Rs{max_prem} satisfying OTM criteria ({moat_meta['rule']})."
        }

    sell_strike = best_sell["strike"]
    sell_sym_info = best_sell["sym_info"]
    sell_ltp = best_sell["ltp"]

    # ── STEP 3: MAP PROTECTIVE HEDGE ARMOR (+/- 500 PTS) ──
    if option_type == "PE":
        hedge_strike = sell_strike - hedge_distance
    else:
        hedge_strike = sell_strike + hedge_distance

    hedge_sym_info = kite_executor.search_option_symbol(chosen_expiry, hedge_strike, option_type)
    hedge_ltp = 0.0
    if hedge_sym_info:
        hedge_ltp = kite_executor.get_ltp(hedge_sym_info["token"], hedge_sym_info["trading_symbol"])

    return {
        "ok": True,
        "direction": direction.upper(),
        "expiry": chosen_expiry,
        "expiry_mode": mode_label,
        "is_fallback": is_fallback,
        "fallback_reason": fallback_reason,
        "sell_strike": sell_strike,
        "sell_option_type": option_type,
        "sell_ltp": sell_ltp,
        "sell_symbol": sell_sym_info["trading_symbol"],
        "sell_token": sell_sym_info["token"],
        "hedge_strike": hedge_strike,
        "hedge_option_type": option_type,
        "hedge_ltp": hedge_ltp,
        "hedge_symbol": hedge_sym_info["trading_symbol"] if hedge_sym_info else f"NIFTY {hedge_strike} {option_type}",
        "hedge_token": hedge_sym_info["token"] if hedge_sym_info else 0,
        "estimated_net_credit": round(sell_ltp - hedge_ltp, 2),
        "spot": spot,
        "supertrend": st_val,
        "moat_rule": moat_meta.get("rule", "")
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARGIN-SAFE ORDER EXECUTION & SQUARE-OFF ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def get_active_w_position() -> Optional[Dict[str, Any]]:
    """Retrieves currently open W1 position from the database, if any."""
    with _w_lock:
        conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM weekly_st_positions WHERE unit_name = 'W1' AND status = 'OPEN' ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None


def execute_weekly_st_entry(candidate: Dict[str, Any], lots: int = 1) -> Dict[str, Any]:
    """
    Executes a fresh Weekly ST spread following the Margin-Safe Invariant:
      Step 1: BUY Hedge Leg (+500 pts OTM) FIRST -> Confirms broker margin relief.
      Step 2: SELL Short Leg (Rs80-100 OTM) SECOND.
      Step 3: Saves active position into weekly_st_positions table.
      Step 4: Dispatches Telegram alert.
    """
    if not candidate.get("ok"):
        return {"ok": False, "message": "Invalid candidate data."}

    lot_size = int(db.get("lot_size", "65"))
    qty = lots * lot_size
    now_str = _ist_now()

    hedge_sym = candidate["hedge_symbol"]
    sell_sym = candidate["sell_symbol"]

    _log(f"Initiating Margin-Safe Entry for W1 ({candidate['direction']}): BUY {hedge_sym} FIRST -> SELL {sell_sym} SECOND", "ORDER")

    # ── STEP 1: BUY HEDGE FIRST ──
    hedge_fill = candidate["hedge_ltp"]
    if kite_executor.ensure_logged_in() and db.get("paper_mode", "NO") == "NO":
        order_id, filled = kite_executor.execute_buy_and_confirm(
            trading_symbol=hedge_sym,
            symbol_token=str(candidate.get("hedge_token", "")),
            qty=qty
        )
        if not filled:
            # Brick 2: Auto-cancel unfilled hedge order immediately
            if order_id:
                try:
                    kite_executor.cancel_order(str(order_id))
                    _log(f"Auto-cancelled unfilled hedge order {order_id} for {hedge_sym}.", "CANCEL")
                except Exception as ex_cn:
                    _log(f"Failed to cancel unfilled hedge order {order_id}: {ex_cn}", "WARN")
            _log(f"Hedge BUY order failed or unfilled for {hedge_sym}. Aborting entry to prevent naked sell!", "ABORT")
            return {"ok": False, "message": f"Hedge buy failed for {hedge_sym}"}
        fill_price = kite_executor.get_order_fill_price(order_id)
        if fill_price > 0:
            hedge_fill = fill_price

    # ── STEP 2: SELL SHORT LEG SECOND ──
    sell_fill = candidate["sell_ltp"]
    if kite_executor.ensure_logged_in() and db.get("paper_mode", "NO") == "NO":
        order_id, filled = kite_executor.execute_sell_and_confirm(
            trading_symbol=sell_sym,
            symbol_token=str(candidate.get("sell_token", "")),
            qty=qty
        )
        if not filled:
            _log(f"CRITICAL: Short leg SELL failed after hedge bought for {sell_sym}!", "ERROR")
            return {"ok": False, "message": f"Short sell failed for {sell_sym}"}
        fill_price = kite_executor.get_order_fill_price(order_id)
        if fill_price > 0:
            sell_fill = fill_price

    # ── STEP 3: PERSIST IN DATABASE ──
    with _w_lock:
        conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO weekly_st_positions (
                unit_name, created_at, updated_at, expiry_date, direction, status, lots,
                sell_strike, sell_option_type, sell_entry_price, sell_symbol, sell_token,
                hedge_strike, hedge_option_type, hedge_entry_price, hedge_symbol, hedge_token,
                realized_pnl, exit_reason
            ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, '')
        """, (
            "W1", now_str, now_str, candidate["expiry"], candidate["direction"], lots,
            candidate["sell_strike"], candidate["sell_option_type"], sell_fill, sell_sym, candidate["sell_token"],
            candidate["hedge_strike"], candidate["hedge_option_type"], hedge_fill, hedge_sym, candidate["hedge_token"]
        ))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()

    net_credit = round(sell_fill - hedge_fill, 2)
    _log(f"✅ W1 Spread deployed successfully (ID #{new_id}) | Net Credit: Rs{net_credit:.2f}", "SUCCESS")

    # ── STEP 4: TELEGRAM NOTIFICATION ──
    try:
        tg_msg = (
            f"⚡ *[WEEKLY ST-2H ENGINE] NEW SPREAD DEPLOYED (W1)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧭 *Regime*: `{candidate['direction']}` (ST 8,2)\n"
            f"📅 *Expiry*: `{candidate['expiry']}`\n"
            f"🔴 *SELL*: `{sell_sym}` @ Rs{sell_fill:.2f} ({lots} Lot/{qty} Qty)\n"
            f"🟢 *HEDGE*: `{hedge_sym}` @ Rs{hedge_fill:.2f} (Armor +500)\n"
            f"💰 *Net Credit*: `Rs{net_credit:.2f}`\n"
            f"⏱️ *Executed*: `{now_str}`"
        )
        tg.send(tg_msg)
    except Exception as e:
        _log(f"Telegram dispatch failed: {e}", "WARN")

    return {"ok": True, "id": new_id, "message": "Spread executed cleanly."}


def close_weekly_st_position(pos_id: int, exit_reason: str = "PULSE_FLIP") -> Dict[str, Any]:
    """
    Squares off an open W1 spread following the Exit Safety Invariant:
      Step 1: BUY to close Short Leg FIRST -> Eliminates short delta risk immediately.
      Step 2: SELL to close Hedge Leg SECOND.
      Step 3: Calculates realized P&L and marks position CLOSED in DB.
      Step 4: Dispatches Telegram alert.
    """
    with _w_lock:
        conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM weekly_st_positions WHERE id = ?", (pos_id,))
        row = cur.fetchone()
        conn.close()

    if not row:
        return {"ok": False, "message": f"Position #{pos_id} not found."}
    
    pos = dict(row)
    if pos["status"] != "OPEN":
        return {"ok": False, "message": f"Position #{pos_id} is already {pos['status']}."}

    lot_size = int(db.get("lot_size", "65"))
    qty = pos["lots"] * lot_size
    now_str = _ist_now()

    sell_sym = pos["sell_symbol"]
    hedge_sym = pos["hedge_symbol"]

    # Live exit price estimation
    sell_exit = kite_executor.get_ltp(pos["sell_token"], sell_sym) if pos["sell_token"] else pos["sell_entry_price"]
    hedge_exit = kite_executor.get_ltp(pos["hedge_token"], hedge_sym) if pos["hedge_token"] else pos["hedge_entry_price"]

    _log(f"Initiating Exit for W1 (#{pos_id}): BUY to close {sell_sym} FIRST -> SELL to close {hedge_sym} SECOND", "EXIT")

    # ── STEP 1: COVER SHORT LEG FIRST ──
    if kite_executor.ensure_logged_in() and db.get("paper_mode", "NO") == "NO":
        order_id, filled = kite_executor.execute_buy_and_confirm(
            trading_symbol=sell_sym,
            symbol_token=str(pos.get("sell_token", "")),
            qty=qty
        )
        if filled:
            fill_price = kite_executor.get_order_fill_price(order_id)
            if fill_price > 0:
                sell_exit = fill_price

    # ── STEP 2: CLOSE HEDGE LEG SECOND ──
    if kite_executor.ensure_logged_in() and db.get("paper_mode", "NO") == "NO":
        order_id, filled = kite_executor.execute_sell_and_confirm(
            trading_symbol=hedge_sym,
            symbol_token=str(pos.get("hedge_token", "")),
            qty=qty
        )
        if filled:
            fill_price = kite_executor.get_order_fill_price(order_id)
            if fill_price > 0:
                hedge_exit = fill_price

    # P&L Calculation:
    # Short Leg P&L: (sell_entry - sell_exit) * qty
    # Hedge Leg P&L: (hedge_exit - hedge_entry) * qty
    short_pnl = (pos["sell_entry_price"] - sell_exit) * qty
    hedge_pnl = (hedge_exit - pos["hedge_entry_price"]) * qty
    total_realized = round(short_pnl + hedge_pnl, 2)

    with _w_lock:
        conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            UPDATE weekly_st_positions
            SET status = 'CLOSED',
                updated_at = ?,
                sell_exit_price = ?,
                hedge_exit_price = ?,
                realized_pnl = ?,
                exit_reason = ?
            WHERE id = ?
        """, (now_str, sell_exit, hedge_exit, total_realized, exit_reason, pos_id))
        conn.commit()
        conn.close()

    _log(f"✅ Position #{pos_id} closed cleanly | Realized P&L: Rs{total_realized:+,.2f} | Reason: {exit_reason}", "SUCCESS")

    try:
        pnl_emoji = "🟢" if total_realized >= 0 else "🔴"
        tg_msg = (
            f"⚡ *[WEEKLY ST-2H ENGINE] SPREAD CLOSED (W1)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Exit Reason*: `{exit_reason}`\n"
            f"{pnl_emoji} *Realized P&L*: `Rs{total_realized:+,.2f}`\n"
            f"🔴 *Sell Leg*: Covered @ Rs{sell_exit:.2f} (Entry: Rs{pos['sell_entry_price']:.2f})\n"
            f"🟢 *Hedge Leg*: Exited @ Rs{hedge_exit:.2f} (Entry: Rs{pos['hedge_entry_price']:.2f})\n"
            f"⏱️ *Closed*: `{now_str}`"
        )
        tg.send(tg_msg)
    except Exception as e:
        _log(f"Telegram dispatch failed: {e}", "WARN")

    return {"ok": True, "realized_pnl": total_realized, "message": "Position closed."}


def kill_all_weekly_st_positions() -> Dict[str, Any]:
    """
    EMERGENCY KILL SWITCH:
      - Immediately squares off any active W1 position at market.
      - Disables autonomous trading switch to prevent re-entry.
      - Dispatches high-priority Emergency Red Alert.
    """
    _log("🚨 EMERGENCY KILL SWITCH TRIGGERED FOR WEEKLY ST-2H ENGINE!", "KILL")
    pos = get_active_w_position()
    
    # Disable trading switch immediately
    db.set("weekly_st_algo_enabled", "OFF")

    if not pos:
        return {"ok": True, "message": "Autonomous trading turned OFF. No open positions were active."}

    res = close_weekly_st_position(pos["id"], exit_reason="EMERGENCY_KILL_SWITCH")
    return {"ok": True, "message": f"🚨 EMERGENCY KILL COMPLETE: Position #{pos['id']} closed. P&L: Rs{res.get('realized_pnl', 0.0):+,.2f}"}


# ─────────────────────────────────────────────────────────────────────────────
# 3-PULSE EVALUATION & MONDAY ROLLOVER DISPATCHER
# ─────────────────────────────────────────────────────────────────────────────

def _now_ist_dt() -> datetime:
    return datetime.now(IST)


def is_pulse_time() -> Tuple[bool, str]:
    """
    Checks if current IST time falls within the 3 daily execution pulse windows on an ACTIVE trading day:
      - Pulse 1: 11:15 AM (11:14:00 - 11:18:00) -- First 2H Candle Close & Monday First-Signal Rollover
      - Pulse 2: 01:15 PM (13:14:00 - 13:18:00) -- Midday 2H Candle Close
      - Pulse 3: 03:10 PM (15:09:00 - 15:15:00) -- Afternoon Wrap Close
    """
    now_dt = _now_ist_dt()
    import utils
    if not utils.is_trading_day(now_dt):
        return False, "MARKET_CLOSED_WEEKEND_OR_HOLIDAY"

    now = now_dt.time()
    
    if dt_time(11, 14) <= now <= dt_time(11, 18):
        return True, "11:15 AM (Pulse 1 - First Signal & Monday Rollover)"
    elif dt_time(13, 14) <= now <= dt_time(13, 18):
        return True, "01:15 PM (Pulse 2)"
    elif dt_time(15, 9) <= now <= dt_time(15, 15):
        return True, "03:10 PM (Pulse 3 - Afternoon Wrap)"
    return False, "BLIND_PERIOD"


def evaluate_weekly_st_pulse(force_pulse: bool = False) -> Dict[str, Any]:
    """
    Core Autonomous Cycle executed at each 2-Hour pulse:
      1. Verifies if autonomous trading switch is ON.
      2. Audits SuperTrend (8, 2) on 2H timeframe.
      3. Checks for Monday First-Signal Rollover (rolls Tuesday weekly contracts to next week at Pulse 1).
      4. If trend flipped, closes existing position and opens opposite spread.
      5. If flat, deploys fresh spread matching current regime.
    """
    import utils
    if not utils.is_trading_day() and not force_pulse:
        return {"ok": False, "message": "Market is closed today (Weekend or NSE Holiday)."}

    is_algo_on = db.get("weekly_st_algo_enabled", "OFF") == "ON"
    if not is_algo_on and not force_pulse:
        return {"ok": False, "message": "Autonomous Trading is currently OFF."}

    in_pulse, pulse_desc = is_pulse_time()
    if not in_pulse and not force_pulse:
        return {"ok": False, "message": f"Outside pulse window. Current status: {pulse_desc}."}

    _log(f"Executing Pulse Audit: {pulse_desc} (Forced: {force_pulse})", "PULSE")

    # 1. SuperTrend 2H Evaluation
    st_data = calculate_supertrend_2h(period=8, multiplier=2.0)
    if not st_data.get("ok"):
        return {"ok": False, "message": "Failed to compute 2H SuperTrend."}

    regime = st_data["regime"]  # "BULLISH" | "BEARISH"
    spot = st_data["spot"]
    st_val = st_data["supertrend"]
    active_pos = get_active_w_position()

    now_dt = datetime.now(IST)
    is_monday = (now_dt.weekday() == 0)
    
    cfg_st = get_weekly_st_settings()
    lots = cfg_st["lots"]
    min_prem = cfg_st["min_prem"]
    max_prem = cfg_st["max_prem"]
    hedge_dist = cfg_st["hedge_dist"]
    eff_mode = cfg_st["expiry_mode"]
    target_exp = cfg_st["target_expiry"]
    buf_spot = cfg_st["min_spot_buffer"]
    buf_st = cfg_st["st_clearance"]

    # 2. Check Monday Rollover (First Signal Rollover on Monday)
    # USER RULE: On Monday, rollover must happen on the FIRST SIGNAL (Pulse 1 @ 11:15 AM), NOT at 03:10 PM!
    if active_pos and (is_monday or (force_pulse and "ROLLOVER" in str(force_pulse))):
        expiries = get_upcoming_weekly_expiries()
        current_weekly = expiries[0] if expiries else ""
        if active_pos["expiry_date"] == current_weekly:
            _log(f"Monday First-Signal Rollover Triggered at {pulse_desc} for position #{active_pos['id']} expiring on {current_weekly}", "ROLLOVER")
            close_weekly_st_position(active_pos["id"], exit_reason="MONDAY_FIRST_SIGNAL_ROLLOVER")
            
            # Deploy fresh into next week
            candidate = hunt_weekly_st_spread(
                direction=regime,
                min_prem=min_prem,
                max_prem=max_prem,
                hedge_distance=hedge_dist,
                force_next_week=True,
                expiry_mode=eff_mode,
                target_expiry=target_exp,
                min_spot_buffer=buf_spot,
                st_clearance=buf_st,
                st_value=st_val,
                spot_val=spot
            )
            if candidate.get("ok"):
                res = execute_weekly_st_entry(candidate, lots=lots)
                return {"ok": True, "message": f"Monday First-Signal Rollover complete: Closed #{active_pos['id']} and rolled to {candidate['expiry']}."}
            else:
                return {"ok": True, "message": f"Monday Rollover closed #{active_pos['id']}, but candidate hunt failed: {candidate.get('message')}"}

    # 3. Position Logic (Flat vs Holding vs Trend Flip)
    if not active_pos:
        _log(f"W1 is Flat. Deploying fresh {regime} spread.", "DEPLOY")
        candidate = hunt_weekly_st_spread(
            direction=regime,
            min_prem=min_prem,
            max_prem=max_prem,
            hedge_distance=hedge_dist,
            expiry_mode=eff_mode,
            target_expiry=target_exp,
            min_spot_buffer=buf_spot,
            st_clearance=buf_st,
            st_value=st_val,
            spot_val=spot
        )
        if candidate.get("ok"):
            res = execute_weekly_st_entry(candidate, lots=lots)
            return {"ok": True, "message": f"Fresh {regime} spread deployed.", "data": res}
        else:
            return {"ok": False, "message": f"Hunter could not find strikes: {candidate.get('message')}"}

    # If position is already open:
    pos_direction = active_pos["direction"]
    if pos_direction == regime:
        _log(f"W1 position #{active_pos['id']} matches current {regime} trend. Holding active spread.", "HOLD")
        return {"ok": True, "message": f"Signal confirmed: {regime}. Active spread maintained."}
    else:
        # Trend FLIP: Close existing opposite spread -> Deploy new spread
        _log(f"TREND FLIP DETECTED! Position is {pos_direction}, but 2H SuperTrend is now {regime}. Reversing...", "FLIP")
        close_weekly_st_position(active_pos["id"], exit_reason=f"TREND_FLIP_TO_{regime}")
        
        # Deploy fresh spread in new direction
        candidate = hunt_weekly_st_spread(
            direction=regime,
            min_prem=min_prem,
            max_prem=max_prem,
            hedge_distance=hedge_dist,
            expiry_mode=eff_mode,
            target_expiry=target_exp,
            min_spot_buffer=buf_spot,
            st_clearance=buf_st,
            st_value=st_val,
            spot_val=spot
        )
        if candidate.get("ok"):
            res = execute_weekly_st_entry(candidate, lots=lots)
            return {"ok": True, "message": f"Trend flip handled: Closed {pos_direction} and deployed {regime}.", "data": res}
        else:
            return {"ok": False, "message": f"Old position closed on flip, but new hunter failed: {candidate.get('message')}"}


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI RENDERER (TAB 7: ⚡ WEEKLY ST-2H COCKPIT)
# ─────────────────────────────────────────────────────────────────────────────

def _render_strike_preview_card(prev: Dict[str, Any], all_weekly_expiries: List[str], cfg_st: Dict[str, Any], mode_label: str = ""):
    """Renders the single authoritative Glassmorphism Strike Preview card in Row 2.5."""
    if not prev:
        return
    if prev.get("ok"):
        cur_exp_d = all_weekly_expiries[0] if all_weekly_expiries else ""
        next_exp_d = all_weekly_expiries[1] if len(all_weekly_expiries) > 1 else ""
        if prev.get("is_fallback"):
            exp_tag = "FALLBACK TO NEXT WEEK"
        elif prev["expiry"] == next_exp_d:
            exp_tag = "NEXT WEEK (DIRECT)"
        elif prev["expiry"] == cur_exp_d:
            exp_tag = "CURRENT WEEK"
        else:
            exp_tag = f"EXPIRY: {prev['expiry']}"

        lot_qty = cfg_st["lots"] * int(db.get("lot_size", "65"))
        net_cred = prev.get("estimated_net_credit", 0.0)
        tot_cred = net_cred * lot_qty
        eff_mode = mode_label or prev.get("expiry_mode", cfg_st.get("expiry_mode", "--"))

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 2px solid #38bdf8; border-radius: 12px; padding: 16px 20px; margin-top: 14px; margin-bottom: 16px; color: #ffffff; box-shadow: 0 4px 16px rgba(56,189,248,0.2);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px;">
                <div>
                    <span style="font-size: 1.10rem; font-weight: 800; color: #38bdf8;">🎯 LIVE STRIKE HUNTER PREVIEW: {prev.get('direction')} SPREAD</span>
                    <span style="background: #0369a1; color: #e0f2fe; font-size: 0.75rem; padding: 3px 10px; border-radius: 6px; font-weight: 700; margin-left: 8px;">{exp_tag}</span>
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8;">
                    Target Expiry: <b style="color: #f8fafc;">{prev.get('expiry')}</b> &bull; Mode: <b style="color: #fde047;">{eff_mode}</b>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 0.88rem;">
                <div style="background: #1e293b; padding: 12px 14px; border-radius: 8px; border-left: 4px solid #ef4444;">
                    <span style="color: #f87171; font-weight: 700;">🔴 Short Leg (Sell):</span><br/>
                    <b style="font-size: 1.10rem; color: #ffffff;">{prev.get('sell_strike')} {prev.get('sell_option_type')}</b> @ <b>₹{prev.get('sell_ltp', 0.0):.2f}</b><br/>
                    <span style="font-size: 0.75rem; color: #94a3b8;">{prev.get('sell_symbol')}</span>
                </div>
                <div style="background: #1e293b; padding: 12px 14px; border-radius: 8px; border-left: 4px solid #10b981;">
                    <span style="color: #34d399; font-weight: 700;">🟢 Hedge Armor (+/-500pt):</span><br/>
                    <b style="font-size: 1.10rem; color: #ffffff;">{prev.get('hedge_strike')} {prev.get('hedge_option_type')}</b> @ <b>₹{prev.get('hedge_ltp', 0.0):.2f}</b><br/>
                    <span style="font-size: 0.75rem; color: #94a3b8;">{prev.get('hedge_symbol')}</span>
                </div>
                <div style="background: #1e293b; padding: 12px 14px; border-radius: 8px; border-left: 4px solid #facc15;">
                    <span style="color: #fde047; font-weight: 700;">💰 Estimated Net Credit:</span><br/>
                    <b style="font-size: 1.20rem; color: #4ade80;">₹{net_cred:.2f}</b> <span style="font-size: 0.78rem; color: #94a3b8;">/ share</span><br/>
                    <span style="font-size: 0.80rem; color: #cbd5e1;">≈ <b>₹{tot_cred:,.2f}</b> for {cfg_st['lots']} Lot ({lot_qty} qty)</span>
                </div>
            </div>
            <div style="margin-top: 12px; font-size: 0.82rem; color: #cbd5e1; background: #020617; padding: 8px 12px; border-radius: 6px; border: 1px solid #1e293b;">
                🛡️ <b>Moat Protection Active:</b> {prev.get('moat_rule', '')}
                {f"<br/>ℹ️ <span style='color:#fbbf24;'>{prev.get('fallback_reason')}</span>" if prev.get('fallback_reason') else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ Strategy Constraint: {prev.get('message', 'No strike satisfies the configured parameters.')}")


def render_weekly_st_tab(portfolio: Optional[Dict[str, Any]] = None):
    """
    Renders the dedicated Tab 7 Cockpit in Streamlit:
      - Big, visible Trade ON / OFF Switch.
      - Big Emergency Kill Switch.
      - Live SuperTrend 2H Status & Candle Pulse clock.
      - Operator Expiry Strategy (Decide & Lock Console).
      - Active W1 Position Cards (Sold leg & Hedge Armor).
      - Configurable Variable Lot Size & Hunter Settings.
      - Historical Audit Table.
    """
    st.markdown("""
        <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                    border: 1px solid #4338ca; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h2 style="color:#ffffff; margin:0; font-size:1.4rem; font-weight:700;">
                        ⚡ WEEKLY SUPERTREND (8,2) 2-HOUR ENGINE (W1 COCKPIT)
                        <span style="font-size:0.75rem; background:#4338ca; color:#a5b4fc; padding:3px 10px; border-radius:12px; margin-left:8px; border:1px solid #6366f1;">
                            🚀 V7.5 MASTER EDITION
                        </span>
                    </h2>
                    <p style="color:#c7d2fe; margin:4px 0 0 0; font-size:0.80rem;">
                        Autonomous 3-Pulse Weekly Option Spreads &bull; 11:15 AM (First Signal & Monday Rollover) | 01:15 PM | 03:10 PM &bull; Margin-Safe Execution
                    </p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── ROW 1: THE BIG VISIBLE TRADE ON / OFF SWITCH & EMERGENCY KILL SWITCH ──
    col_switch, col_kill = st.columns([1.6, 1.4])

    algo_on = db.get("weekly_st_algo_enabled", "OFF") == "ON"

    with col_switch:
        if algo_on:
            st.markdown("""
                <div style="background:#ecfdf5; border:2px solid #10b981; border-radius:10px; padding:12px 18px; text-align:center; margin-bottom:10px;">
                    <span style="font-size:1.25rem; font-weight:800; color:#065f46;">🟢 AUTONOMOUS TRADING IS ACTIVE (ON)</span><br/>
                    <span style="font-size:0.75rem; color:#047857;">Engine will automatically audit and execute at 11:15 AM, 1:15 PM & 3:10 PM</span>
                </div>
            """, unsafe_allow_html=True)
            if st.button("⏹️ PAUSE / TURN TRADING OFF", key="btn_w_toggle_off", type="secondary", use_container_width=True):
                db.set("weekly_st_algo_enabled", "OFF")
                st.toast("⏸️ Weekly ST Autonomous Trading PAUSED.", icon="⏸️")
                st.rerun()
        else:
            st.markdown("""
                <div style="background:#fef2f2; border:2px solid #ef4444; border-radius:10px; padding:12px 18px; text-align:center; margin-bottom:10px;">
                    <span style="font-size:1.25rem; font-weight:800; color:#991b1b;">🔴 AUTONOMOUS TRADING IS PAUSED (OFF)</span><br/>
                    <span style="font-size:0.75rem; color:#b91c1c;">Engine is currently IDLE. No automated orders will be dispatched.</span>
                </div>
            """, unsafe_allow_html=True)
            if st.button("▶️ ACTIVATE / TURN TRADING ON", key="btn_w_toggle_on", type="primary", use_container_width=True):
                db.set("weekly_st_algo_enabled", "ON")
                st.toast("🚀 Weekly ST Autonomous Trading ACTIVATED!", icon="🟢")
                st.rerun()

    with col_kill:
        st.markdown("""
            <div style="background:#fff1f2; border:1px solid #fecdd3; border-radius:10px; padding:12px 18px; text-align:center; margin-bottom:10px;">
                <span style="font-size:0.95rem; font-weight:700; color:#9f1239;">🚨 EMERGENCY SAFETY CONSOLE</span><br/>
                <span style="font-size:0.75rem; color:#be123c;">1-Click Instant Market Exit of all open W1 legs</span>
            </div>
        """, unsafe_allow_html=True)
        if st.session_state.get("confirm_w_kill"):
            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button("🔥 YES, KILL POSITIONS NOW", key="btn_w_kill_confirm", type="primary", use_container_width=True):
                    res = kill_all_weekly_st_positions()
                    st.session_state["confirm_w_kill"] = False
                    st.error(res["message"])
                    st.rerun()
            with c_no:
                if st.button("❌ Cancel", key="btn_w_kill_cancel", use_container_width=True):
                    st.session_state["confirm_w_kill"] = False
                    st.rerun()
        else:
            if st.button("🚨 EMERGENCY KILL SWITCH", key="btn_w_kill_prompt", type="secondary", use_container_width=True):
                st.session_state["confirm_w_kill"] = True
                st.rerun()

    st.markdown("<br/>", unsafe_allow_html=True)

    # ── ROW 2: LIVE SUPERTREND (8,2) 2H METRICS & TIMELINE CLOCK ──
    force_ref = st.session_state.pop("w_force_st_refresh", False)
    st_info = calculate_supertrend_2h(period=8, multiplier=2.0, force_refresh=force_ref)
    in_pulse, pulse_text = is_pulse_time()

    col_title_left, col_title_right = st.columns([3, 1])
    with col_title_left:
        st.markdown(f"""
            <div style="font-size:0.85rem; color:#475569; margin-bottom:8px;">
                ⏱️ <b>Calculation Mode:</b> Zerodha Kite Native 2-Hour Candle RMA &bull; Lookback: 120 Days (300+ bars) &bull; 
                <span style="color:#0284c7; font-weight:600;">⚡ Real-time Spot Injected</span> &bull; 
                <i>Refreshed: {_ist_now()}</i>
            </div>
        """, unsafe_allow_html=True)
    with col_title_right:
        if st.button("🔄 Refresh SuperTrend", key="btn_w_refresh_st", use_container_width=True):
            st.session_state["w_force_st_refresh"] = True
            st.rerun()

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("NIFTY 50 SPOT", f"₹{st_info.get('spot', 0.0):,.2f}")
    with col_m2:
        regime = st_info.get("regime", "NEUTRAL")
        r_color = "🟢" if regime == "BULLISH" else "🔴"
        st.metric("SUPERTREND (8, 2)", f"₹{st_info.get('supertrend', 0.0):,.2f}", f"{r_color} {regime}")
    with col_m3:
        st.metric("SPOT DISTANCE", f"{st_info.get('distance', 0.0):+,.2f} pts", f"{st_info.get('distance_pct', 0.0):+,.2f}%")
    with col_m4:
        st.metric("PULSE CLOCK", pulse_text, "Active Window" if in_pulse else "Blind Watch")

    st.markdown("""
        <div style="background:#f8fafc; border-left:4px solid #6366f1; padding:8px 14px; border-radius:4px; font-size:0.78rem; color:#334155; margin-top:8px;">
            <b>⚡ Update & Execution Cadence:</b><br/>
            &bull; <b>Cockpit Display:</b> Dynamic Spot & SuperTrend refresh on page load or on clicking <b>'🔄 Refresh SuperTrend'</b> (cached 60s for Kite API safety).<br/>
            &bull; <b>Autonomous Order Pulses:</b> Trades are executed strictly at 2-Hour candle closes to eliminate whipsaws: 
            <b>11:15 AM (Pulse 1 & Monday First-Signal Rollover)</b>, <b>01:15 PM (Pulse 2)</b>, and <b>03:10 PM (Pulse 3 Afternoon Wrap)</b>.<br/>
            &bull; <b>Monday Rollover Rule:</b> On Monday, rollover executes on the <b>FIRST SIGNAL (Pulse 1 @ 11:15 AM)</b>. Any open position expiring on Tuesday is immediately rolled over into Next Week's Expiry.
        </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── ROW 2.5: DECIDE & LOCK WEEKLY EXPIRY & SUPERTREND MOAT CONSOLE ──
    cfg_st = get_weekly_st_settings()
    is_w_locked = cfg_st["locked"]
    cur_exp_mode = cfg_st["expiry_mode"]
    all_weekly_expiries = get_upcoming_weekly_expiries()

    st.markdown('<p style="font-size:1.15rem; font-weight:800; color:#1e1b4b; margin: 12px 0 6px 0;">🎛️ WEEKLY EXPIRY & SUPERTREND MOAT STRATEGY (DECIDE & LOCK)</p>', unsafe_allow_html=True)

    mode_options = [
        "🔘 Auto (Safety First) [Recommended]: Prioritizes current week; auto-shifts to Next Week if SuperTrend moat is violated",
        "🔘 Force Next Week: Skips current week entirely; strictly trades Next Week",
        "🔘 Force Current Week: Trades current week only; strictly enforces SuperTrend moat"
    ]

    if "NEXT" in cur_exp_mode:
        default_mode_idx = 1
    elif "CURRENT" in cur_exp_mode:
        default_mode_idx = 2
    else:
        default_mode_idx = 0

    if is_w_locked:
        # LOCKED & ARMED VIEW
        lock_time = cfg_st["locked_at"] or "Active"
        target_display = cfg_st["target_expiry"] if cfg_st["target_expiry"] else ("Next Week (Direct)" if "NEXT" in cur_exp_mode else ("Current Week (Direct)" if "CURRENT" in cur_exp_mode else "Dynamic Auto-Shift"))
        mode_badge = "🔘 Force Next Week" if "NEXT" in cur_exp_mode else ("🔘 Force Current Week" if "CURRENT" in cur_exp_mode else "🔘 Auto (Safety First)")
        
        cur_regime = st_info.get("regime", "NEUTRAL")
        cur_spot = st_info.get("spot", 0.0)
        cur_st = st_info.get("supertrend", 0.0)
        buf_s = cfg_st["min_spot_buffer"]
        buf_m = cfg_st["st_clearance"]
        
        if cur_regime == "BULLISH":
            max_pe = min(cur_spot - buf_s, cur_st - buf_m) if cur_st > 0 else (cur_spot - buf_s)
            moat_desc = f"🛡️ Moat Protected: Short PE Strike must be <= ₹{int(max_pe)} ({buf_m:.0f} pts below ST support ₹{cur_st:.1f} & {buf_s:.0f} pts below Spot)"
        else:
            min_ce = max(cur_spot + buf_s, cur_st + buf_m) if cur_st > 0 else (cur_spot + buf_s)
            moat_desc = f"🛡️ Moat Protected: Short CE Strike must be >= ₹{int(min_ce)} ({buf_m:.0f} pts above ST resistance ₹{cur_st:.1f} & {buf_s:.0f} pts above Spot)"

        st.markdown(f'''
        <div style="background: linear-gradient(135deg, #052e16 0%, #064e3b 100%); border: 2px solid #10b981; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.15rem; font-weight: 800; color: #34d399;">
                        🔒 WEEKLY EXPIRY & MOAT STRATEGY LOCKED & ARMED
                    </span>
                    <span style="background: #022c22; color: #6ee7b7; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; font-weight: 700; margin-left: 8px;">
                        LOCKED AT {lock_time}
                    </span>
                    <div style="font-size: 0.88rem; color: #e2e8f0; margin-top: 6px;">
                        Mode: <b style="color: #fde047;">{mode_badge}</b> &bull; Expiry: <b style="color: #93c5fd;">{target_display}</b> &bull; Spot Buffer: <b>{buf_s:.0f} pts</b> &bull; ST Moat: <b>{buf_m:.0f} pts</b>
                    </div>
                    <div style="font-size: 0.82rem; color: #a7f3d0; margin-top: 4px; font-weight: 600;">
                        {moat_desc}
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        c_un1, c_un2 = st.columns([1.5, 2.5])
        with c_un1:
            if st.button("🔓 UNLOCK & EDIT EXPIRY STRATEGY", key="btn_w_unlock", use_container_width=True):
                db.set("weekly_st_expiry_locked", "0")
                st.session_state.pop("w_hunter_preview", None)
                st.toast("Strategy unlocked. Returned to Draft Mode.", icon="🔓")
                st.rerun()
        with c_un2:
            if st.button("🎯 Refresh Live Strike Scan (Armed Strategy)", key="btn_w_refresh_armed_preview", type="secondary", use_container_width=True):
                target_regime = st_info.get("regime", "BULLISH")
                with st.spinner("Scanning compliant strikes with Armed Strategy..."):
                    preview_res = hunt_weekly_st_spread(
                        direction=target_regime if target_regime in ("BULLISH", "BEARISH") else "BULLISH",
                        min_prem=cfg_st["min_prem"],
                        max_prem=cfg_st["max_prem"],
                        hedge_distance=cfg_st["hedge_dist"],
                        expiry_mode=cur_exp_mode,
                        target_expiry=cfg_st["target_expiry"],
                        min_spot_buffer=cfg_st["min_spot_buffer"],
                        st_clearance=cfg_st["st_clearance"],
                        st_value=cur_st,
                        spot_val=cur_spot
                    )
                    st.session_state["w_hunter_preview"] = preview_res
                    st.rerun()

        # In-Place Strategy Preview Display Card in Row 2.5 (Locked Mode)
        prev_locked = st.session_state.get("w_hunter_preview")
        if prev_locked:
            _render_strike_preview_card(prev_locked, all_weekly_expiries, cfg_st, mode_label=mode_badge)

    else:
        # UNLOCKED DRAFT VIEW
        st.markdown('''
        <div style="background: #1e1b10; border: 2px solid #f59e0b; border-radius: 12px; padding: 14px 18px; margin-bottom: 14px; color: #ffffff;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #fbbf24;">
                ⚠️ WEEKLY EXPIRY STRATEGY IN DRAFT MODE (DECIDE & LOCK)
            </div>
            <div style="font-size: 0.82rem; color: #fef3c7; margin-top: 4px;">
                Choose how the engine selects weekly option expiry. Click <b>'🔒 LOCK & ARM EXPIRY STRATEGY'</b> to enforce during autonomous pulses.
            </div>
        </div>
        ''', unsafe_allow_html=True)

        sel_mode_str = st.radio(
            "Select Weekly Expiry Strategy Mode",
            mode_options,
            index=default_mode_idx,
            key="w_radio_mode"
        )
        
        if "Force Next Week" in sel_mode_str:
            new_mode = "FORCE_NEXT"
        elif "Force Current Week" in sel_mode_str:
            new_mode = "FORCE_CURRENT"
        else:
            new_mode = "AUTO"

        c_exp1, c_exp2, c_exp3 = st.columns([2, 1, 1])
        with c_exp1:
            exp_options = all_weekly_expiries[:4] if all_weekly_expiries else ["2026-10-06", "2026-10-13"]
            cur_target = cfg_st["target_expiry"]
            exp_idx = exp_options.index(cur_target) if cur_target in exp_options else 0
            sel_target_exp = st.selectbox(
                "Manual Expiry Date Override (Optional)",
                exp_options,
                index=exp_idx,
                key="w_sel_target_exp",
                help="Applies when specific expiry date targeting is needed."
            )
        with c_exp2:
            new_spot_buf = st.number_input("Min Spot Buffer (pts)", min_value=50, max_value=500, value=int(cfg_st["min_spot_buffer"]), step=25, key="w_num_spot_buf")
        with c_exp3:
            new_st_moat = st.number_input("ST Moat Clearance (pts)", min_value=0, max_value=300, value=int(cfg_st["st_clearance"]), step=25, key="w_num_st_moat")

        # Live calculation preview
        cur_regime = st_info.get("regime", "NEUTRAL")
        cur_spot = st_info.get("spot", 0.0)
        cur_st = st_info.get("supertrend", 0.0)
        if cur_regime == "BULLISH":
            max_pe = min(cur_spot - new_spot_buf, cur_st - new_st_moat) if cur_st > 0 else (cur_spot - new_spot_buf)
            moat_desc = f"🛡️ <b>Moat Rule:</b> Short PE strike must be <b><= ₹{int(max_pe)}</b> (strictly protected by SuperTrend Support ₹{cur_st:.1f})"
        else:
            min_ce = max(cur_spot + new_spot_buf, cur_st + new_st_moat) if cur_st > 0 else (cur_spot + new_spot_buf)
            moat_desc = f"🛡️ <b>Moat Rule:</b> Short CE strike must be <b>>= ₹{int(min_ce)}</b> (strictly protected by SuperTrend Resistance ₹{cur_st:.1f})"

        st.markdown(f"""
            <div style="background:#f1f5f9; border-left:4px solid #0284c7; padding:8px 14px; border-radius:4px; font-size:0.80rem; color:#0f172a; margin: 8px 0 14px 0;">
                {moat_desc}
            </div>
        """, unsafe_allow_html=True)

        # ── STEP 1: PREVIEW & HUNT CANDIDATE SPREAD ──────────────────────────
        if st.button("🎯 STEP 1: PREVIEW & HUNT STRIKES WITH THIS STRATEGY", key="btn_w_test_preview", use_container_width=True, type="primary"):
            with st.spinner("Hunting compliant strikes..."):
                preview_res = hunt_weekly_st_spread(
                    direction=cur_regime,
                    min_prem=cfg_st["min_prem"],
                    max_prem=cfg_st["max_prem"],
                    hedge_distance=cfg_st["hedge_dist"],
                    expiry_mode=new_mode,
                    target_expiry=sel_target_exp,
                    min_spot_buffer=float(new_spot_buf),
                    st_clearance=float(new_st_moat),
                    st_value=cur_st,
                    spot_val=cur_spot
                )
                st.session_state["w_hunter_preview"] = preview_res
                st.rerun()

        # In-Place Strategy Preview Display Card in Row 2.5 (Draft Mode)
        prev_draft = st.session_state.get("w_hunter_preview")
        if prev_draft:
            _render_strike_preview_card(prev_draft, all_weekly_expiries, cfg_st, mode_label=new_mode)
            st.markdown('<div style="margin-top:12px;"></div>', unsafe_allow_html=True)
            if st.button("🔒 STEP 2: CONFIRM & LOCK EXPIRY STRATEGY", key="btn_w_lock", type="primary", use_container_width=True):
                set_weekly_st_settings(
                    locked=True,
                    expiry_mode=new_mode,
                    target_expiry=sel_target_exp,
                    min_spot_buffer=float(new_spot_buf),
                    st_clearance=float(new_st_moat)
                )
                st.toast(f"✅ Expiry Strategy LOCKED: {new_mode}", icon="🔒")
                st.rerun()


    st.markdown("<br/>", unsafe_allow_html=True)

    # ── ROW 3: ACTIVE W1 POSITION CARDS ──
    st.markdown("### 📦 Active W1 Spread Pod")
    pos = get_active_w_position()

    if not pos:
        st.info("⚪ **W1 UNIT IS CURRENTLY FLAT (0 Open Positions).** Engine is standing by for the next pulse signal.")
    else:
        # Fetch live LTPs for active position
        sell_ltp = kite_executor.get_ltp(pos["sell_token"], pos["sell_symbol"]) if pos["sell_token"] else pos["sell_entry_price"]
        hedge_ltp = kite_executor.get_ltp(pos["hedge_token"], pos["hedge_symbol"]) if pos["hedge_token"] else pos["hedge_entry_price"]
        
        lot_size = int(db.get("lot_size", "65"))
        qty = pos["lots"] * lot_size
        
        short_pnl = (pos["sell_entry_price"] - sell_ltp) * qty
        hedge_pnl = (hedge_ltp - pos["hedge_entry_price"]) * qty
        net_pnl = short_pnl + hedge_pnl

        pnl_color = "#16a34a" if net_pnl >= 0 else "#dc2626"
        dir_badge = "🟢 BULL PUT SPREAD" if pos["direction"] == "BULLISH" else "🔴 BEAR CALL SPREAD"

        st.markdown(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:16px 20px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div>
                        <span style="font-size:1.1rem; font-weight:700; color:#1e293b;">W1 AUTONOMOUS POD</span>
                        <span style="font-size:0.80rem; background:#f1f5f9; padding:3px 8px; border-radius:6px; margin-left:8px; font-weight:600;">{dir_badge}</span>
                        <span style="font-size:0.80rem; color:#64748b; margin-left:8px;">Exp: <b>{pos['expiry_date']}</b> &bull; Qty: <b>{qty} ({pos['lots']} Lot)</b></span>
                    </div>
                    <div>
                        <span style="font-size:1.25rem; font-weight:800; font-family:'JetBrains Mono',monospace; color:{pnl_color};">
                            {'+' if net_pnl >= 0 else ''}₹{net_pnl:,.2f}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown(f"""
                <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:8px; padding:12px 16px;">
                    <div style="font-size:0.75rem; color:#991b1b; font-weight:700;">🔴 SHORT LEG (SELL)</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#1e293b; margin:4px 0;">{pos['sell_symbol']}</div>
                    <div style="font-size:0.82rem; color:#475569;">
                        Entry: <b>₹{pos['sell_entry_price']:.2f}</b> | LTP: <b>₹{sell_ltp:.2f}</b><br/>
                        Leg P&L: <b style="color:{'#16a34a' if short_pnl >= 0 else '#dc2626'}; font-family:'JetBrains Mono';">{'+' if short_pnl >= 0 else ''}₹{short_pnl:,.2f}</b>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col_c2:
            st.markdown(f"""
                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:12px 16px;">
                    <div style="font-size:0.75rem; color:#166534; font-weight:700;">🟢 HEDGE ARMOR (BUY +500 PTS)</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#1e293b; margin:4px 0;">{pos['hedge_symbol']}</div>
                    <div style="font-size:0.82rem; color:#475569;">
                        Entry: <b>₹{pos['hedge_entry_price']:.2f}</b> | LTP: <b>₹{hedge_ltp:.2f}</b><br/>
                        Leg P&L: <b style="color:{'#16a34a' if hedge_pnl >= 0 else '#dc2626'}; font-family:'JetBrains Mono';">{'+' if hedge_pnl >= 0 else ''}₹{hedge_pnl:,.2f}</b>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)
        if st.button("🛑 1-Click Clean Exit W1 Spread (Short First -> Hedge Second)", key="btn_w_manual_exit", use_container_width=True):
            close_res = close_weekly_st_position(pos["id"], exit_reason="MANUAL_UI_EXIT")
            st.success(close_res["message"])
            st.rerun()

    st.divider()

    # ── ROW 4: CONFIGURATION & VARIABLE LOTS (VARIABLE TESTING) ──
    with st.expander("⚙️ Autonomous Configuration & Risk Settings", expanded=False):
        c_cfg1, c_cfg2, c_cfg3, c_cfg4 = st.columns(4)
        with c_cfg1:
            curr_lots = int(db.get("weekly_st_lots", "1"))
            in_lots = st.number_input("Trading Lots (Variable)", min_value=1, max_value=50, value=curr_lots, step=1, key="in_w_lots")
            if in_lots != curr_lots:
                db.set("weekly_st_lots", str(in_lots))
                st.toast(f"Lots updated to {in_lots}", icon="✅")
        with c_cfg2:
            min_p = float(db.get("weekly_st_target_prem_min", "80.0"))
            in_min_p = st.number_input("Min Target Premium (₹)", min_value=10.0, max_value=300.0, value=min_p, step=5.0, key="in_w_min_p")
            if in_min_p != min_p:
                db.set("weekly_st_target_prem_min", str(in_min_p))
        with c_cfg3:
            max_p = float(db.get("weekly_st_target_prem_max", "100.0"))
            in_max_p = st.number_input("Max Target Premium (₹)", min_value=20.0, max_value=400.0, value=max_p, step=5.0, key="in_w_max_p")
            if in_max_p != max_p:
                db.set("weekly_st_target_prem_max", str(in_max_p))
        with c_cfg4:
            h_dist = int(db.get("weekly_st_hedge_dist", "500"))
            in_h_dist = st.number_input("Hedge Armor Distance (pts)", min_value=100, max_value=2000, value=h_dist, step=100, key="in_w_h_dist")
            if in_h_dist != h_dist:
                db.set("weekly_st_hedge_dist", str(in_h_dist))

    # ── ROW 5: PULSE ENGINE DIAGNOSTICS & MANUAL FORCE-TRIGGER TOOLS ──
    with st.expander("🛠️ Pulse Engine Diagnostic & Manual Force-Trigger Tools", expanded=False):
        st.markdown("""
        <div style="font-size:0.84rem; color:#94a3b8; margin-bottom:12px;">
            Audits the automated 2-Hour SuperTrend pulse timing, execution state, and allows manual watchdog force-firing for testing.
        </div>
        """, unsafe_allow_html=True)
        c_diag1, c_diag2 = st.columns([1.5, 2.5])
        with c_diag1:
            if st.button("🚀 Force Run Pulse Evaluation Now (Test)", key="btn_w_force_pulse", use_container_width=True):
                with st.spinner("Evaluating 2H SuperTrend Pulse..."):
                    res = evaluate_weekly_st_pulse(force_pulse=True)
                    if res.get("ok"):
                        st.success(res.get("message", "Pulse evaluated successfully."))
                    else:
                        st.warning(res.get("message", "Pulse skipped or completed with warnings."))
                    st.rerun()
        with c_diag2:
            st.info(f"⏱️ **Watchdog Status:** {'Active Pulse Window' if in_pulse else 'Blind Watch'} | SuperTrend: ₹{st_info.get('supertrend', 0.0):,.2f}")

    # ── ROW 6: TRADE LOGS & AUDIT HISTORY ──
    with st.expander("📜 W1 Trade History & Audit Log", expanded=False):
        with _w_lock:
            conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
            df_hist = pd.read_sql_query("SELECT * FROM weekly_st_positions ORDER BY id DESC LIMIT 25", conn)
            conn.close()

        if df_hist.empty:
            st.caption("No historical W1 trades found.")
        else:
            display_cols = [c for c in ["id", "created_at", "updated_at", "direction", "status", "lots", "sell_symbol", "sell_entry_price", "sell_exit_price", "hedge_symbol", "hedge_entry_price", "hedge_exit_price", "realized_pnl", "exit_reason"] if c in df_hist.columns]
            st.dataframe(df_hist[display_cols], use_container_width=True)
