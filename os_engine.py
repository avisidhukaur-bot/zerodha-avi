"""
os_engine.py -- Pure Option Price Momentum Engine (3:00 PM Option Selling Line)
==============================================================================
Strategy: "3:15 Ka Jaadu" / Operator 2-Step Option Selling Engine
Reference: Arjun & Mentor 3:15 Story + Pure Option Price Action

Operational Workflow:
  1. Expiry Selection: Weekly vs Monthly contract horizon.
  2. Step 1: Operator clicks "Fetch Relevant Strike Price & Hedge Price".
       - Scans 100-multiple strikes <= Rs150 for both Call and Put.
       - Fetches live LTP and yesterday's reference price (exchange previous close).
       - Evaluates decay: Today LTP < Yesterday Price => DECAYING (Qualified).
       - Maps 500-point OTM protective hedge ("Helmet Rule").
       - Computes 1.382 Stop Loss trigger (+38.2%).
  3. Step 2: Anytime Execution with 1-Trade-Per-Day Guard:
       - Operator can execute anytime (morning, 1 PM, 2 PM, evening) or arm for 3:00 PM.
       - Enforces: "Din mein sirf ek hi baar trade karna hai" (Max 1 trade/day).
       - Buys 500-pt Hedge FIRST on broker terminal before short selling.
  4. Autonomous "Stopwatch" (1.382 Stop Loss Rule):
       - Monitors continuous individual 1.382 Stop Loss trigger.
       - If hit, short leg auto-exits; long hedge retained as orphan capital shield.
  5. Daily 3:00 PM Decision & Multi-Day Holding:
       - Trade continues for Day 2, 3, 4 while option stays below 3:00 PM line.
       - If option cuts above line => Auto-closed at market at 15:00 IST!
       - Full manual override available anytime.
"""

import sys
import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
import pytz
import pandas as pd
import streamlit as st

import db
import config as cfg
import utils
from kite_executor import kite_executor
import block_manager as bm
import pnl_engine as pe
import telegram_bot as tg

IST = pytz.timezone("Asia/Kolkata")

# Default Parameters
DEFAULT_TARGET_PREMIUM = 150.0
DEFAULT_HEDGE_DISTANCE = 500
DEFAULT_SL_MULTIPLIER = 1.382
STRIKE_STEP = 100


def _log(msg: str, tag: str = "OS") -> None:
    """Standardized logger with tag."""
    utils.log(f"[{tag}] {msg}", tag)


def _ist_now() -> str:
    """Current IST datetime string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# OPTION ANCHORS & YESTERDAY REFERENCE PRICE LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

def get_yesterday_reference_price(trading_symbol: str, symbol_token: str = "", force_refresh: bool = False) -> float:
    """
    Fetches the verified yesterday reference price for an option contract:
      1. If not force_refresh, checks SQLite cache (VALID ONLY IF SAVED TODAY).
      2. Queries Kite quote API for official exchange previous close:
         kite.quote(["NFO:TRADINGSYMBOL"])["ohlc"]["close"]
      3. Saves verified official previous close in SQLite date-stamped for today.
    """
    clean_sym = str(trading_symbol).strip().upper()
    if not force_refresh:
        anchor = db.get_os_strike_anchor(clean_sym)
        if anchor > 0.0:
            return anchor

    # 2. Query live quote from Kite for official exchange previous close
    if kite_executor.ensure_logged_in():
        try:
            query = f"NFO:{clean_sym}"
            res = kite_executor.kite.quote([query])
            if query in res:
                ohlc = res[query].get("ohlc", {})
                prev_close = float(ohlc.get("close", 0.0) or 0.0)
                if prev_close > 0.0:
                    set_option_anchor(clean_sym, prev_close)
                    _log(f"Verified NSE previous close for {clean_sym}: Rs{prev_close:.2f}", "ANCHOR")
                    return prev_close
        except Exception as e:
            _log(f"Quote previous close lookup failed for {clean_sym}: {e}", "WARN")

    # Fallback to local cache if Kite API was temporarily unreachable
    anchor = db.get_os_strike_anchor(clean_sym)
    if anchor > 0.0:
        return anchor

    return 0.0


def set_option_anchor(trading_symbol: str, price: float) -> None:
    """Saves yesterday reference anchor price for this specific option symbol with today's date."""
    clean_sym = str(trading_symbol).strip().upper()
    db.set_os_strike_anchor(clean_sym, price)
    _log(f"Anchor updated for {clean_sym}: Rs{price:.2f}", "ANCHOR")


def refresh_all_os_anchors() -> int:
    """
    Scans all active OS blocks, open strikes, and locked configuration candidate strikes.
    Fetches the official NSE previous day close (ohlc['close']) from Kite API and caches
    it in the database date-stamped for today.
    Also purges any stale multi-day anchors from previous sessions.
    Returns the count of anchors successfully refreshed.
    """
    db.prune_stale_os_anchors()

    if not kite_executor.ensure_logged_in():
        _log("Cannot refresh OS anchors: Kite not logged in.", "WARN")
        return 0

    symbols_to_refresh = set()

    # Active OS blocks and strikes
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    os_blocks = [b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper().startswith("OS")]
    for b in os_blocks:
        open_strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
        for s in open_strikes:
            sym_info = bm._resolve_symbol(s)
            if sym_info and sym_info.get("trading_symbol"):
                symbols_to_refresh.add(sym_info["trading_symbol"])

    # Locked configuration candidate strikes if any
    saved_cfg = db.get_os_settings()
    if saved_cfg.get("locked"):
        exp = saved_cfg.get("expiry_date", "")
        if exp:
            try:
                insp = inspect_os_candidates(exp, target_premium=float(saved_cfg.get("target_premium", DEFAULT_TARGET_PREMIUM)))
                ce_cand = insp.get("ce", {})
                pe_cand = insp.get("pe", {})
                if ce_cand.get("sell_tradingsymbol"):
                    symbols_to_refresh.add(ce_cand["sell_tradingsymbol"])
                if pe_cand.get("sell_tradingsymbol"):
                    symbols_to_refresh.add(pe_cand["sell_tradingsymbol"])
            except Exception as e:
                _log(f"Error inspecting candidate strikes during anchor refresh: {e}", "WARN")

    if not symbols_to_refresh:
        _log("No active OS contracts to refresh.", "ANCHOR")
        return 0

    refreshed = 0
    for sym in symbols_to_refresh:
        try:
            prev_close = get_yesterday_reference_price(sym, force_refresh=True)
            if prev_close > 0.0:
                refreshed += 1
                _log(f"[REFRESH] Anchor cached for {sym}: NSE Close Rs{prev_close:.2f}", "ANCHOR")
        except Exception as e:
            _log(f"Failed to refresh anchor for {sym}: {e}", "WARN")

    return refreshed


# ─────────────────────────────────────────────────────────────────────────────
# EXPIRY RESOLUTION (WEEKLY VS MONTHLY)
# ─────────────────────────────────────────────────────────────────────────────

def get_categorized_expiries() -> Dict[str, List[str]]:
    """
    Returns available Nifty expiries cleanly categorized into 'weekly' and 'monthly'.
    """
    try:
        df = kite_executor._load_security_master()
        if df.empty:
            return {"all": [], "weekly": [], "monthly": []}

        nifty_opts = df[(df["name"] == "NIFTY") & (df["exchange"] == "NFO") & (df["instrument_type"].isin(["CE", "PE"]))]
        expiries = sorted(nifty_opts["expiry"].dropna().unique())
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        valid_expiries = [exp for exp in expiries if str(exp) >= today_str]
        if not valid_expiries:
            valid_expiries = expiries[:10]

        # Group by Year-Month to find the monthly expiry (last expiry of each month)
        from collections import defaultdict
        month_groups = defaultdict(list)
        for exp in valid_expiries:
            ym = str(exp)[:7]  # YYYY-MM
            month_groups[ym].append(exp)

        monthly_set = set()
        for ym, exp_list in month_groups.items():
            # Last expiry in that month is the monthly contract
            monthly_set.add(exp_list[-1])

        weekly_list = [exp for exp in valid_expiries if exp not in monthly_set]
        monthly_list = [exp for exp in valid_expiries if exp in monthly_set]

        return {
            "all": valid_expiries,
            "weekly": weekly_list if weekly_list else valid_expiries[:4],
            "monthly": monthly_list if monthly_list else valid_expiries[4:]
        }
    except Exception as e:
        _log(f"Error categorizing expiries: {e}", "ERROR")
        return {"all": [], "weekly": [], "monthly": []}


def get_nifty_expiry_dates() -> List[str]:
    """Returns flat list of valid Nifty option expiries."""
    cat = get_categorized_expiries()
    return cat.get("all", [])



def _normalize_expiry(exp_str: str) -> str:
    """Normalizes any date string to YYYY-MM-DD."""
    if not exp_str:
        return ""
    s = str(exp_str).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def get_expiry_step_size(expiry_date: str) -> int:
    """
    V5.4 Dynamic Step Selector:
    - Near Month (DTE <= 30 days) -> 100 Multiples
    - Far / Next Month (DTE > 30 days) -> 500 Multiples (Guarantees institutional liquidity)
    """
    try:
        norm_exp = _normalize_expiry(expiry_date)
        if norm_exp:
            exp_dt = datetime.strptime(norm_exp, "%Y-%m-%d").date()
            today = datetime.now(IST).date()
            dte = (exp_dt - today).days
            if dte > 30:
                return 500
    except Exception:
        pass
    return 100


get_strike_step = get_expiry_step_size


def get_occupied_strikes(expiry_date: str) -> List[int]:
    """
    V5.4 Zero-Clash Strike Shield:
    Scans active non-OS units (M1, M2, M3...) and live broker positions for the same expiry.
    Returns list of strike prices currently in use so OS engine avoids collisions.
    """
    occupied = set()
    norm_exp = _normalize_expiry(expiry_date)
    try:
        # 1. Active Blocks in DB (M1, M2, M3...)
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        for b in active_blocks:
            uname = (b.get("anchor_unit_name") or "").strip().upper()
            if not uname.startswith("OS"):
                b_exp = _normalize_expiry(b.get("expiry_date", ""))
                if b_exp == norm_exp:
                    strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
                    for s in strikes:
                        sp = s.get("strike_price")
                        if sp and float(sp) > 0:
                            occupied.add(int(float(sp)))
    except Exception as e:
        _log(f"DB occupied strikes query note: {e}", "DEBUG")

    # 2. Broker live positions (for matching expiry, excluding OS unit's own strikes)
    try:
        broker_mod = None
        if hasattr(kite_executor, "get_net_positions"):
            broker_mod = kite_executor
        elif hasattr(bm, "kite_executor"):
            broker_mod = bm.kite_executor
        if broker_mod:
            # Collect strikes belonging to active OS units so they aren't marked as M-unit collisions
            os_strikes = set()
            for b in active_blocks:
                if (b.get("anchor_unit_name") or "").strip().upper().startswith("OS"):
                    for s in db.get_strikes_by_block(b["block_id"], status_filter="OPEN"):
                        sp_val = s.get("strike_price")
                        if sp_val:
                            os_strikes.add(int(float(sp_val)))

            pos_list = broker_mod.get_net_positions()
            for p in pos_list:
                if p.get("net_qty", 0) != 0:
                    p_exp = _normalize_expiry(p.get("expiry_date", ""))
                    if not p_exp or p_exp == norm_exp:
                        sp = p.get("strike_price")
                        if sp and float(sp) > 0:
                            sp_int = int(float(sp))
                            if sp_int not in os_strikes:
                                occupied.add(sp_int)
    except Exception as be:
        _log(f"Broker positions occupied strikes check note: {be}", "DEBUG")

    return sorted(list(occupied))


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC STRIKE HUNTER (100 / 500 MULTIPLES) & CANDIDATE INSPECTOR
# ─────────────────────────────────────────────────────────────────────────────

def hunt_os_strike(
    option_type: str,
    expiry_date: str,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER,
    occupied_strikes: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Hunts candidate option contract in dynamic multiples (100 for near, 500 for far month):
      - Avoids collisions with active M-Units via Zero-Clash Strike Shield.
      - Finds strike with premium <= target_premium (with 500-step premium flex).
      - Queries yesterday's closing reference price.
      - Evaluates decay: Today LTP < Yesterday Price.
      - Pairs with liquid OTM hedge (also on step multiple).
      - Computes 1.382 Stop Loss trigger.
    """
    opt_type = option_type.strip().upper()
    if opt_type not in ("CE", "PE"):
        return {"ok": False, "message": f"Invalid option type: {option_type}. Must be CE or PE."}

    df = kite_executor._load_security_master()
    if df.empty:
        return {"ok": False, "message": "Security master is empty. Cannot scan option chain."}

    # Normalize expiry string to YYYY-MM-DD
    exp_yyyy_mm_dd = _normalize_expiry(expiry_date)
    step_size = get_expiry_step_size(exp_yyyy_mm_dd)
    if occupied_strikes is None:
        occupied_strikes = get_occupied_strikes(exp_yyyy_mm_dd)

    subset = df[
        (df["name"].str.upper() == "NIFTY") &
        (df["exchange"].str.upper() == "NFO") &
        (df["expiry"] == exp_yyyy_mm_dd) &
        (df["instrument_type"].str.upper() == opt_type)
    ]

    if subset.empty:
        return {"ok": False, "message": f"No NIFTY {opt_type} contracts found for expiry {exp_yyyy_mm_dd}."}

    # 1. MANUAL STRIKE OVERRIDE
    if manual_strike and manual_strike > 0:
        sell_strike = int(manual_strike)
        sell_row = subset[subset["strike"] == float(sell_strike)]
        if sell_row.empty:
            return {"ok": False, "message": f"Strike {sell_strike} {opt_type} not found for expiry {exp_yyyy_mm_dd}."}

        sell_item = sell_row.iloc[0]
        sell_token = str(sell_item["instrument_token"])
        sell_tsymbol = str(sell_item["tradingsymbol"])
        sell_ltp = kite_executor.get_ltp(sell_token, sell_tsymbol)
    else:
        # 2. AUTO HUNTER: 50-ENDING SERIES (V8.1 — Mathematical Zero-Clash with M-Units)
        # OS1 strictly hunts 50-ENDING strikes (22550, 22650, 22750, 22850, 22950...)
        # M-Units (M1, M2, M3) occupy EXACT 100-multiples (22600, 22800, 23000...).
        # 50-ending strikes are mathematically NON-overlapping with M-Unit 100-multiples.
        # Visual ID rule: ends in 50 = OS trade | ends in 00 = M-Unit trade.
        fifty_series = subset[(subset["strike"] % 100 == 50)].copy()
        candidates_pool = fifty_series if not fifty_series.empty else subset

        live_spot = kite_executor.get_nifty_spot()
        if live_spot > 0:
            if opt_type == "CE":
                candidates = candidates_pool[candidates_pool["strike"] >= live_spot - 300].copy()
                candidates = candidates.sort_values("strike").head(10)
            else:
                candidates = candidates_pool[candidates_pool["strike"] <= live_spot + 300].copy()
                candidates = candidates.sort_values("strike", ascending=False).head(10)
            if candidates.empty:
                candidates = candidates_pool.head(10)
        else:
            candidates = candidates_pool.head(10)

        queries = [f"NFO:{ts}" for ts in candidates["tradingsymbol"]]
        ltp_dict = {}
        if kite_executor.ensure_logged_in() and queries:
            try:
                for i in range(0, len(queries), 50):
                    batch = queries[i:i+50]
                    res = kite_executor.kite.ltp(batch)
                    for k, v in res.items():
                        sym = k.replace("NFO:", "")
                        ltp_dict[sym] = float(v.get("last_price", 0.0))
            except Exception as e:
                _log(f"Batch LTP query error: {e}", "WARN")

        scored_candidates = []
        for _, row in candidates.iterrows():
            tsym = str(row["tradingsymbol"])
            tok = str(row["instrument_token"])
            strike_val = int(row["strike"])
            ltp = ltp_dict.get(tsym, 0.0)
            if ltp <= 0.0:
                ltp = kite_executor.get_ltp(tok, tsym)

            if ltp > 0.0:
                scored_candidates.append({
                    "strike": strike_val,
                    "token": tok,
                    "tradingsymbol": tsym,
                    "ltp": ltp,
                    "row": row
                })

        if not scored_candidates:
            return {"ok": False, "message": f"Could not fetch live LTPs for {opt_type} option chain."}

        today_str = datetime.now().strftime("%Y-%m-%d")
        min_floor = max(105.0, target_premium * 0.70)

        # Disqualify strikes below min floor (₹105 hard floor), occupied strikes, and strikes cut today
        eligible = [
            c for c in scored_candidates
            if c["ltp"] >= min_floor
            and int(c["strike"]) not in occupied_strikes
            and db.get(f"os_strike_cut_{c['strike']}_{opt_type}_{today_str}") != "1"
        ]

        if not eligible:
            _log(f"OS Hunter {opt_type}: No eligible contracts >= min floor Rs{min_floor:.2f} (Target Rs{target_premium:.2f}). System sits quiet.", "GUARD")
            return {
                "ok": False,
                "message": f"NO TRADE QUALIFIED: All decaying contracts are below minimum floor Rs{min_floor:.2f} (Target Rs{target_premium:.2f}). System sits quiet."
            }

        # Check decay for candidates against yesterday reference
        decaying_eligible = []
        for c in eligible:
            y_anc = get_yesterday_reference_price(c["tradingsymbol"])
            if y_anc <= 0.0 or c["ltp"] < y_anc:
                decaying_eligible.append(c)

        # Select candidate nearest to target_premium (can be above or below, e.g. Rs135 or Rs160 nearest to Rs150)
        if decaying_eligible:
            selected = min(decaying_eligible, key=lambda x: abs(x["ltp"] - target_premium))
        else:
            selected = min(eligible, key=lambda x: abs(x["ltp"] - target_premium))

        sell_strike = selected["strike"]
        sell_token = selected["token"]
        sell_tsymbol = selected["tradingsymbol"]
        sell_ltp = selected["ltp"]

    # 3. OTM HEDGE RESOLUTION ("Helmet Rule")
    actual_hedge_dist = hedge_dist
    if step_size == 500:
        actual_hedge_dist = max(500, ((hedge_dist + 499) // 500) * 500)
    else:
        actual_hedge_dist = max(100, ((hedge_dist + 99) // 100) * 100)

    if opt_type == "CE":
        hedge_strike = sell_strike + actual_hedge_dist
    else:
        hedge_strike = sell_strike - actual_hedge_dist

    hedge_row = subset[subset["strike"] == float(hedge_strike)]
    if hedge_row.empty:
        hedge_candidates = subset[subset["strike"] > sell_strike] if opt_type == "CE" else subset[subset["strike"] < sell_strike]
        if not hedge_candidates.empty:
            hedge_row = hedge_candidates.iloc[-1:] if opt_type == "CE" else hedge_candidates.iloc[:1]
        else:
            return {"ok": False, "message": f"Could not find {actual_hedge_dist}-pt OTM hedge strike {hedge_strike} {opt_type}."}

    hedge_item = hedge_row.iloc[0]
    hedge_strike_actual = int(hedge_item["strike"])
    hedge_token = str(hedge_item["instrument_token"])
    hedge_tsymbol = str(hedge_item["tradingsymbol"])
    hedge_ltp = kite_executor.get_ltp(hedge_token, hedge_tsymbol)

    # 4. YESTERDAY REFERENCE PRICE & OPTION DECAY EVALUATION
    yesterday_anchor = get_yesterday_reference_price(sell_tsymbol, sell_token)
    if yesterday_anchor <= 0.0:
        # If unavailable, use current LTP as display reference (NEVER save sell_ltp as yesterday anchor in DB!)
        yesterday_anchor = sell_ltp

    # Decaying only if sell_ltp is strictly lower than verified yesterday anchor
    is_decaying = (sell_ltp < yesterday_anchor) if (yesterday_anchor > 0 and yesterday_anchor != sell_ltp) else False
    decay_diff = yesterday_anchor - sell_ltp

    # 5. 1.382 STOP LOSS CALCULATION
    sl_base = sell_ltp if sell_ltp > 0 else target_premium
    sl_price = round(sl_base * sl_multiplier, 2)
    sl_pct = round((sl_multiplier - 1.0) * 100.0, 1)

    return {
        "ok": True,
        "option_type": opt_type,
        "expiry_date": exp_yyyy_mm_dd,
        "sell_strike": sell_strike,
        "sell_token": sell_token,
        "sell_tradingsymbol": sell_tsymbol,
        "sell_ltp": sell_ltp,
        "yesterday_anchor": yesterday_anchor,
        "is_decaying": is_decaying,
        "decay_diff": decay_diff,
        "hedge_strike": hedge_strike_actual,
        "hedge_token": hedge_token,
        "hedge_tradingsymbol": hedge_tsymbol,
        "hedge_ltp": hedge_ltp,
        "hedge_distance": abs(hedge_strike_actual - sell_strike),
        "sl_price": sl_price,
        "sl_pct": sl_pct,
        "sl_multiplier": sl_multiplier,
        "target_premium": target_premium,
        "step_size": step_size,
        "occupied_strikes_avoided": [s for s in occupied_strikes if abs(s - sell_strike) <= step_size]
    }


def inspect_os_candidates(
    expiry_date: str,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_ce_strike: Optional[int] = None,
    manual_pe_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER
) -> Dict[str, Any]:
    """
    Step 1 Inspection Function:
    Fetches both Call and Put candidates for the chosen expiry,
    audits their yesterday reference price, enforces Zero-Clash Strike Shield,
    and determines overall qualification.
    """
    norm_exp = _normalize_expiry(expiry_date)
    occupied = get_occupied_strikes(norm_exp)

    hunt_ce = hunt_os_strike("CE", expiry_date, target_premium, manual_ce_strike, hedge_dist, sl_multiplier, occupied_strikes=occupied)
    hunt_pe = hunt_os_strike("PE", expiry_date, target_premium, manual_pe_strike, hedge_dist, sl_multiplier, occupied_strikes=occupied)

    ce_ok = hunt_ce.get("ok", False) and hunt_ce.get("is_decaying", False)
    pe_ok = hunt_pe.get("ok", False) and hunt_pe.get("is_decaying", False)

    if ce_ok and pe_ok:
        action = "SELL_BOTH"
        status_msg = "Both Call & Put options are decaying below yesterday's reference price. QUALIFIED TO SELL BOTH!"
    elif ce_ok and not pe_ok:
        action = "SELL_CE_ONLY"
        status_msg = "Only Call option is decaying. Put is expanding. QUALIFIED TO SELL CALL ONLY!"
    elif not ce_ok and pe_ok:
        action = "SELL_PE_ONLY"
        status_msg = "Only Put option is decaying. Call is expanding. QUALIFIED TO SELL PUT ONLY!"
    else:
        action = "NO_TRADE"
        status_msg = "High VIX / Market Spiking: Both Call & Put are trading above yesterday's price. NO TRADE!"

    return {
        "ok": hunt_ce.get("ok", False) or hunt_pe.get("ok", False),
        "expiry_date": expiry_date,
        "ce": hunt_ce,
        "pe": hunt_pe,
        "ce_qualified": ce_ok,
        "pe_qualified": pe_ok,
        "action": action,
        "status_msg": status_msg,
        "occupied_strikes": occupied
    }



# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT ENGINE (WITH 1-TRADE-PER-DAY GUARD)
# ─────────────────────────────────────────────────────────────────────────────

def deploy_os_wing(
    block_id: int,
    hunt_data: dict,
    lots: int = 1,
    deploy_now: bool = True
) -> Dict[str, Any]:
    """Deploys a single hedged wing (CE or PE) into an OS block."""
    opt_type = hunt_data["option_type"]
    sell_strike = hunt_data["sell_strike"]
    hedge_strike = hunt_data["hedge_strike"]
    sell_ltp = hunt_data["sell_ltp"]
    sl_price = hunt_data["sl_price"]
    sl_pct = hunt_data["sl_pct"]
    expiry_date = hunt_data["expiry_date"]

    hedge_res = bm.add_strike_to_block(
        block_id=block_id,
        strike_price=hedge_strike,
        option_type=opt_type,
        leg_type="HEDGE_BUY",
        anchor_price=hunt_data["hedge_ltp"] if hunt_data["hedge_ltp"] > 0 else 1.0,
        lots=lots,
        expiry_date=expiry_date,
        trade_state="PENDING"
    )
    if not hedge_res.get("ok"):
        return {"ok": False, "message": f"Failed to add {opt_type} hedge strike: {hedge_res.get('message')}"}
    h_id = hedge_res["strike_id"]

    anchor_p = sell_ltp if sell_ltp > 0 else hunt_data.get("target_premium", DEFAULT_TARGET_PREMIUM)
    sell_res = bm.add_strike_to_block(
        block_id=block_id,
        strike_price=sell_strike,
        option_type=opt_type,
        leg_type="SELL",
        anchor_price=anchor_p,
        lots=lots,
        expiry_date=expiry_date,
        sl_price=sl_price,
        sl_pct=sl_pct,
        reentry_enabled=0,
        trade_state="PENDING"
    )
    if not sell_res.get("ok"):
        return {"ok": False, "message": f"Failed to add {opt_type} sell strike: {sell_res.get('message')}"}
    s_id = sell_res["strike_id"]

    bm.link_hedge_to_sell(s_id, h_id)

    exec_msg = "Armed in PENDING for 3:00 PM."
    if deploy_now:
        exec_res = bm.execute_strike(s_id)
        if exec_res.get("ok"):
            exec_msg = f"LIVE EXECUTED: Bought {hedge_strike} {opt_type} (+500 pts), Sold {sell_strike} {opt_type} (SL: Rs{sl_price:.2f})."
        else:
            exec_msg = f"Execution note: {exec_res.get('message')}"
            return {
                "ok": False,
                "sell_strike_id": s_id,
                "hedge_strike_id": h_id,
                "message": exec_msg
            }

    return {
        "ok": True,
        "sell_strike_id": s_id,
        "hedge_strike_id": h_id,
        "message": exec_msg
    }


def deploy_os_unit(
    unit_name: str = "OS1",
    expiry_date: str = "",
    lots: int = 3,
    lot_size: Optional[int] = None,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_ce_strike: Optional[int] = None,
    manual_pe_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER,
    deploy_now: bool = True,
    force_override_daily_limit: bool = False,
    is_manual: bool = False
) -> Dict[str, Any]:
    """
    Deploys qualified decaying OS wings:
      - Strictly respects operator's locked lots (no arbitrary system overrides).
      - Prevents duplicate side overlap: If Put or Call leg is already running in this unit,
        it does NOT add another duplicate wing on that side.
      - Auto Trade Separation: 3:02 PM auto-audit fires once per day. Manual trades by
        an operator are completely free to execute anytime (1, 2, 3... times).
      - Long hedge is bought FIRST on broker terminal.
    """
    unit_name = str(unit_name).strip().upper()
    if not unit_name.startswith("OS"):
        unit_name = f"OS_{unit_name}"

    # Strict Lot Size Adherence from Locked Settings
    saved_cfg = db.get_os_settings()
    if saved_cfg.get("locked"):
        lots = int(saved_cfg.get("lots", lots) or lots)
        if not lot_size:
            lot_size = int(saved_cfg.get("lot_size", 65) or 65)
        if not expiry_date:
            expiry_date = saved_cfg.get("expiry_date", "")
        if not target_premium or target_premium == DEFAULT_TARGET_PREMIUM:
            target_premium = float(saved_cfg.get("target_premium", DEFAULT_TARGET_PREMIUM))

    # Manual user lot size persistence
    if lot_size and int(lot_size) > 0:
        db.set_os_lot_size(int(lot_size))
        _log(f"Manual lot size set to {lot_size} units per lot by operator.", "CONFIG")

    effective_lot_size = db.get_os_lot_size()
    total_qty = lots * effective_lot_size

    # Enforce daily 1-trade limit ONLY for scheduled 3:02 PM Auto-Trade (Manual trades are unrestricted)
    if deploy_now and not is_manual and not force_override_daily_limit:
        if db.has_os_auto_traded_today(unit_name):
            msg = f"BLOCKED: 3:02 PM Auto-Trade for Unit {unit_name} has already executed today!"
            _log(msg, "BLOCKED")
            return {"ok": False, "action": "BLOCKED_DAILY_LIMIT", "message": msg}

    if not expiry_date:
        expiries = get_nifty_expiry_dates()
        if not expiries:
            return {"ok": False, "message": "No valid Nifty option expiries found."}
        expiry_date = expiries[0]

    inspection = inspect_os_candidates(
        expiry_date=expiry_date,
        target_premium=target_premium,
        manual_ce_strike=manual_ce_strike,
        manual_pe_strike=manual_pe_strike,
        hedge_dist=hedge_dist,
        sl_multiplier=sl_multiplier
    )

    action = inspection["action"]
    hunt_ce = inspection["ce"]
    hunt_pe = inspection["pe"]

    if action == "NO_TRADE":
        msg = "NO TRADE TAKEN: Both Call and Put options are trading above their yesterday price (High VIX). Capital protected!"
        _log(msg, "SKIP")
        return {"ok": True, "action": "NO_TRADE", "message": msg}

    # Create or retrieve active block
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    existing_b = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == unit_name), None)

    if existing_b:
        block_id = existing_b["block_id"]
        db.update_block_recommended_lots(block_id, lots)
        # Clean up any stale unexecuted PENDING strikes in this block to prevent duplicates
        stale_pending = db.get_strikes_by_block(block_id, status_filter="PENDING")
        for sp in stale_pending:
            db.delete_strike(sp["strike_id"])
    else:
        res_b = bm.create_block(
            expiry_date=expiry_date,
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name=unit_name,
            master_anchor_price=0.0,
            regime_buffer=0.0,
            custom_lots=lots
        )
        if not res_b.get("ok"):
            return {"ok": False, "message": f"Failed to create block: {res_b.get('message')}"}
        block_id = res_b["block_id"]

    # Check what legs are ALREADY OPEN in this unit/block to prevent duplicate overlap
    existing_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN") if existing_b else []
    has_open_ce = any(s.get("option_type") == "CE" and s.get("leg_type") == "SELL" for s in existing_strikes)
    has_open_pe = any(s.get("option_type") == "PE" and s.get("leg_type") == "SELL" for s in existing_strikes)

    deployed_actions = []
    error_actions = []

    # 1. Call Wing Evaluation
    if inspection["ce_qualified"]:
        if has_open_ce:
            _log(f"Unit {unit_name} already has an OPEN CE position in Block {block_id}. Skipping CE to avoid overlap.", "SKIP")
        else:
            res_ce = deploy_os_wing(block_id, hunt_ce, lots=lots, deploy_now=deploy_now)
            if res_ce.get("ok"):
                deployed_actions.append(f"Sold {hunt_ce['sell_strike']} CE (Hedge: {hunt_ce['hedge_strike']} CE)")
            else:
                error_actions.append(f"CE: {res_ce.get('message')}")

    # 2. Put Wing Evaluation
    if inspection["pe_qualified"]:
        if has_open_pe:
            _log(f"Unit {unit_name} already has an OPEN PE position in Block {block_id}. Skipping PE to avoid overlap.", "SKIP")
        else:
            res_pe = deploy_os_wing(block_id, hunt_pe, lots=lots, deploy_now=deploy_now)
            if res_pe.get("ok"):
                deployed_actions.append(f"Sold {hunt_pe['sell_strike']} PE (Hedge: {hunt_pe['hedge_strike']} PE)")
            else:
                error_actions.append(f"PE: {res_pe.get('message')}")

    if error_actions and not deployed_actions:
        return {
            "ok": False,
            "action": action,
            "block_id": block_id,
            "unit_name": unit_name,
            "message": f"Deployment failed: {' | '.join(error_actions)}"
        }

    # If all qualified wings were skipped due to existing positions
    if not deployed_actions:
        if has_open_ce and has_open_pe:
            msg = f"Unit {unit_name}: Both CE and PE wings already active. No duplicate overlap permitted."
        elif has_open_pe and not inspection["ce_qualified"]:
            msg = f"Unit {unit_name}: PE already open. CE candidate is expanding (not decaying). No overlap taken."
        elif has_open_ce and not inspection["pe_qualified"]:
            msg = f"Unit {unit_name}: CE already open. PE candidate is expanding (not decaying). No overlap taken."
        else:
            msg = f"Unit {unit_name}: No decaying wings deployed."
        _log(msg, "SKIP")
        return {"ok": True, "action": "NO_OVERLAP", "message": msg}

    summary_msg = " | ".join(deployed_actions)

    # Mark trade taken
    if deploy_now:
        db.mark_os_traded_today(unit_name)
        if not is_manual:
            db.mark_os_auto_traded_today(unit_name)

    try:
        exec_mode_label = "MANUAL OPERATOR EXECUTION" if is_manual else "3:02 PM AUTO-PILOT"
        tg.send(
            f"🎯 <b>OS ENGINE DEPLOYMENT — {unit_name}</b> 🎯\n"
            f"Mode: <b>{exec_mode_label}</b>\n"
            f"Expiry: {expiry_date}\n"
            f"Action: <b>{summary_msg}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Lots</b>: {lots} lot(s)\n"
            f"<b>Manual Lot Size</b>: {effective_lot_size} Qty/Lot\n"
            f"<b>Total Traded Qty</b>: {total_qty} units\n"
            f"<b>Stop Loss Rule</b>: 1.382x Entry (+38.2%)\n"
            f"<b>Overlap Guard</b>: Active (No duplicate side entries allowed)."
        )
    except Exception as e:
        _log(f"Error sending TG deploy alert: {e}", "WARN")

    return {
        "ok": True,
        "action": action,
        "block_id": block_id,
        "unit_name": unit_name,
        "lots": lots,
        "lot_size": effective_lot_size,
        "total_qty": total_qty,
        "message": f"Unit {unit_name} deployed: {summary_msg} (Qty: {total_qty})"
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3:00 PM OPTION SELLING LINE AUDIT & CONTINUATION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_os_3pm_decision() -> Dict[str, Any]:
    """
    Evaluates running trades and candidate options at 15:02 IST:
      1. Running Trades:
         - Today 3:02 PM LTP < Yesterday 3 PM Price => CONTINUATION (Hold for Day 2, 3, 4).
         - Today 3:02 PM LTP >= Yesterday 3 PM Price => AUTO-CLOSE (Cut above line).
      2. Rolls over today's 3:02 PM price as tomorrow's anchor.
    """
    _log("⏰ 15:02 IST: Running 3:02 PM Option Selling Line Audit...", "DECISION")

    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    os_blocks = [b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper().startswith("OS")]

    results = []

    for b in os_blocks:
        block_id = b["block_id"]
        unit_name = (b.get("anchor_unit_name") or f"OS{b['block_number']}").strip().upper()
        expiry_date = b.get("expiry_date", "")
        lots = int(b.get("custom_lots") or 1)

        open_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN")
        open_sells = [s for s in open_strikes if s.get("leg_type") == "SELL"]

        if open_sells:
            for s in open_sells:
                s_id = s["strike_id"]
                stk = s["strike_price"]
                opt = s["option_type"]
                ltp = pe.fetch_ltp(s, force_refresh=True)

                sym_info = bm._resolve_symbol(s)
                tsym = sym_info["trading_symbol"] if sym_info else f"NIFTY_{stk}_{opt}"
                yest_anchor = get_yesterday_reference_price(tsym)
                if yest_anchor <= 0.0:
                    yest_anchor = float(s.get("anchor_price") or 0.0)

                # V5.5 SAFETY GUARD: If LTP fetch failed (0.0), skip audit — never auto-close on bad data
                if ltp <= 0.0:
                    _log(f"{unit_name}: Cannot audit {stk} {opt}: live LTP returned Rs0.0. Skipping audit to protect position.", "WARN")
                    continue
                # V5.5 SAFETY GUARD: If anchor is 0 (never set / stale), skip audit — never auto-close on bad anchor
                if yest_anchor <= 0.0:
                    _log(f"{unit_name}: Cannot audit {stk} {opt}: anchor price is Rs0.0 (not set). Skipping audit.", "WARN")
                    continue

                if ltp <= yest_anchor:
                    # CONTINUATION (Holding the line or decaying)
                    db.update_strike_trade_state(s_id, "CONTINUED")
                    _log(f"{unit_name}: {stk} {opt} SELL CONTINUED overnight (LTP Rs{ltp:.2f} <= Line Rs{yest_anchor:.2f}).", "OK")
                    results.append(f"• <b>{unit_name}</b>: CONTINUED {stk} {opt} (LTP Rs{ltp:.2f} &le; Line Rs{yest_anchor:.2f})")
                else:
                    # AUTO-CLOSE (Strictly rose above 3:00 PM line: ltp > yest_anchor)
                    _log(f"{unit_name}: 🛑 LINE CUT! {stk} {opt} SELL rose above 3:00 PM line (LTP Rs{ltp:.2f} > Rs{yest_anchor:.2f}). Auto-closing...", "EXIT")
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    db.set(f"os_strike_cut_{stk}_{opt}_{today_str}", "1")
                    _log(f"🚫 Anti-Churn Guard: Blacklisted {stk} {opt} from re-entry for today {today_str}.", "GUARD")

                    # Synchronous exit: close short strike AND linked hedge immediately
                    bm.close_strike(s_id, close_hedge=True)
                    db.update_strike_trade_state(s_id, "CLOSED")
                    h_id = s.get("hedge_strike_id")
                    if h_id:
                        bm.close_strike(h_id, close_hedge=False)
                        db.update_strike_trade_state(h_id, "CLOSED")

                    results.append(f"• <b>{unit_name}</b>: 🛑 AUTO-CLOSED {stk} {opt} (LTP Rs{ltp:.2f} &gt; Line Rs{yest_anchor:.2f})")

                if ltp > 0:
                    set_option_anchor(tsym, ltp)


    # ── Phase 2: 15:02 IST Auto-Deploy for Locked / Armed Pods ────────────────
    try:
        saved_cfg = db.get_os_settings()
        if saved_cfg.get("locked"):
            for pod_unit in ["OS1", "OS2", "OS3"]:
                if not db.has_os_auto_traded_today(pod_unit):
                    s_exp = saved_cfg.get("expiry_date", "")
                    s_lots = int(saved_cfg.get("lots", 2) or 2)
                    s_ls = int(saved_cfg.get("lot_size", 65) or 65)
                    s_tp = float(saved_cfg.get("target_premium", DEFAULT_TARGET_PREMIUM))
                    s_mode = saved_cfg.get("mode", "AUTO")
                    s_ce = saved_cfg.get("manual_ce") if s_mode == "MANUAL" else None
                    s_pe = saved_cfg.get("manual_pe") if s_mode == "MANUAL" else None

                    _log(f"⏰ 15:02 IST Auto-Deploy triggering for locked pod {pod_unit} (Lots: {s_lots})...", "AUTODEPLOY")
                    res_deploy = deploy_os_unit(
                        unit_name=pod_unit,
                        expiry_date=s_exp,
                        lots=s_lots,
                        lot_size=s_ls,
                        target_premium=s_tp,
                        manual_ce_strike=s_ce,
                        manual_pe_strike=s_pe,
                        deploy_now=True,
                        force_override_daily_limit=False,
                        is_manual=False
                    )
                    act = res_deploy.get("action", "")
                    msg = res_deploy.get("message", "")
                    db.mark_os_auto_traded_today(pod_unit)
                    if act != "BLOCKED_DAILY_LIMIT":
                        results.append(f"• <b>{pod_unit} 15:01 Auto-Deploy</b>: {msg}")
                    break  # Deployed primary locked pod
    except Exception as auto_e:
        _log(f"Error in 15:01 IST OS Auto-Deploy: {auto_e}", "ERROR")

    try:

        text = "\n".join(results) if results else "• No active OS pods with running positions."
        tg.send(
            f"⏰ <b>15:01 IST OPTION SELLING LINE AUDIT</b> ⏰\n"
            f"Option Decay Evaluation Complete (Staggered Window 15:01 - 15:04):\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{text}"
        )
    except Exception as e:
        _log(f"Error sending 3PM TG alert: {e}", "WARN")

    return {"ok": True, "results": results}


def wipe_out_and_reset_os_unit(unit_name: str = "OS1") -> Dict[str, Any]:
    """
    1-Click OS Wipe Out & Clean Slate Reset (V5.5):
      1. Finds all blocks associated with this OS unit (e.g. OS1).
      2. Safely closes any open SELL or HEDGE legs on Zerodha broker terminal.
      3. Cascades and permanently purges/force deletes the block(s) from SQLite DB.
      4. Unlocks OS settings, reverting UI to fresh Draft Mode for the next month contract.
      5. Clears daily trade flags so the unit is 100% unlocked.
    """
    unit_name = str(unit_name).strip().upper()
    if not unit_name.startswith("OS"):
        unit_name = f"OS_{unit_name}"

    _log(f"[WIPE_OUT] Initiating permanent wipe out and reset for {unit_name}...", "ALERT")

    all_blocks = db.get_all_blocks()
    os_blocks = [b for b in all_blocks if (b.get("anchor_unit_name") or "").strip().upper() == unit_name]

    legs_closed = 0
    blocks_purged = 0
    errors = []

    for b in os_blocks:
        bid = b["block_id"]
        # Step A: Close open legs on broker
        try:
            kill_res = bm.kill_block(bid)
            legs_closed += kill_res.get("closed_count", 0)
        except Exception as ke:
            errors.append(f"Broker close Block #{b.get('block_number')}: {ke}")

        # Step B: Cascade force delete from SQLite DB
        try:
            ok_del = db.force_delete_block(bid)
            if ok_del:
                blocks_purged += 1
        except Exception as de:
            errors.append(f"DB delete Block #{b.get('block_number')}: {de}")

    # Step C: Unlock OS settings back to Draft state
    db.unlock_os_settings()

    # Step D: Reset daily trade flag & cut strike flags
    db.reset_os_daily_trade_flag(unit_name)
    db.set(f"last_os_auto_trade_date_{unit_name}", "")

    # Step E: Send Telegram confirmation alert
    try:
        tg.send(
            f"💥 <b>{unit_name} WIPE OUT & RESET EXECUTED</b>\n"
            f"Broker Legs Closed: {legs_closed}\n"
            f"DB Blocks Purged: {blocks_purged}\n"
            f"Settings: Reset to Draft Mode (Clean Slate) ✅\n"
            f"Ready for next contract deployment."
        )
    except Exception:
        pass

    msg = f"Successfully wiped out and reset {unit_name}! Closed {legs_closed} live leg(s), purged {blocks_purged} block(s). OS is now in fresh Draft Mode."
    _log(msg, "SUCCESS")
    return {
        "ok": len(errors) == 0,
        "legs_closed": legs_closed,
        "blocks_purged": blocks_purged,
        "message": msg,
        "errors": errors
    }


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI RENDERER FOR TAB 2
# ─────────────────────────────────────────────────────────────────────────────

def render_os_tab(portfolio: dict) -> None:
    """
    Renders the dedicated Option Selling (OS) Tab in Streamlit with the
    operator's 2-step workflow:
      1. Expiry Horizon selection (Weekly vs Monthly).
      2. Step 1: "Fetch Relevant Strike Price & Hedge Price" inspection.
      3. Step 2: Anytime execution with 1-trade/day guard or Arm for 3:00 PM.
      4. Active OS Pod Cockpit with 1-Click Profit Lock.
    """
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1.5px solid #ff5722; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="font-size: 1.25rem; font-weight: 700; color: #ffffff;">
                    💎 Option Selling Engine (V8.1 — 50-Ending Series & Zero-Clash Shield Edition)
                </span>
                <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 4px;">
                    Operator 2-Step Workflow &bull; 50-Ending Strike Hunter &bull; Zero-Clash Shield &bull; Visual M-Unit vs OS Identity &bull; Unrestricted Manual Trades
                </div>
            </div>
            <div style="margin-top: 8px;">
                <span style="background: rgba(255, 87, 34, 0.2); border: 1px solid #ff5722; color: #ff8a65; font-size: 0.75rem; padding: 4px 12px; border-radius: 20px; font-weight: 600;">
                    V8.1 ACTIVE
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. LOAD SETTINGS & LOCK STATUS
    saved_cfg = db.get_os_settings()
    is_locked = saved_cfg.get("locked", False)

    cat_expiries = get_categorized_expiries()
    all_expiries = cat_expiries.get("all", ["2026-09-29"])

    if is_locked:
        # ---------------------------------------------------------------------
        # LOCKED & ARMED STATE (AUTO-PILOT READY)
        # ---------------------------------------------------------------------
        s_horizon = saved_cfg.get("horizon", "Weekly Expiry")
        s_exp = saved_cfg.get("expiry_date", "")
        s_lots = saved_cfg.get("lots", 1)
        s_ls = saved_cfg.get("lot_size", 65)
        s_total_qty = s_lots * s_ls
        s_mode = saved_cfg.get("mode", "AUTO")
        s_ce = saved_cfg.get("manual_ce", 0)
        s_pe = saved_cfg.get("manual_pe", 0)
        s_tp = saved_cfg.get("target_premium", 150.0)
        s_locked_at = saved_cfg.get("locked_at", "")

        mode_badge = f"🎯 Manual Strikes ({s_ce} CE / {s_pe} PE)" if s_mode == "MANUAL" else f"🏹 Auto Hunter (&le; ₹{s_tp:.1f})"

        st.markdown(f'''
        <div style="background: #04241a; border: 2px solid #10b981; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.2rem; font-weight: 800; color: #34d399;">
                        🔒 OS SETTINGS LOCKED & ARMED
                    </span>
                    <span style="background: #064e3b; color: #a7f3d0; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; font-weight: 700; margin-left: 10px;">
                        SYSTEM ACTIVE
                    </span>
                    <div style="font-size: 0.90rem; color: #ffffff; margin-top: 6px;">
                        Locked on: <b style="color: #a7f3d0;">{s_locked_at}</b> &bull; Parameters are frozen and ready for 3:00 PM audit or manual execution.
                    </div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 14px; background: #021a13; padding: 14px; border-radius: 8px; font-size: 0.92rem; color: #ffffff;">
                <div>📅 <b style="color: #93c5fd;">Horizon:</b> {s_horizon}</div>
                <div>🎯 <b style="color: #93c5fd;">Expiry Date:</b> {s_exp}</div>
                <div>📦 <b style="color: #93c5fd;">Lots & Size:</b> {s_lots} Lot(s) &times; {s_ls} Qty = <b style="color: #fde047;">{s_total_qty} units</b></div>
                <div>⚡ <b style="color: #93c5fd;">Strategy Mode:</b> <span style="color: #34d399; font-weight: 700;">{mode_badge}</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        col_l1, col_l2, col_l3 = st.columns([1.2, 1.8, 2.0])
        with col_l1:
            if st.button("🔓 Unlock Settings", key="btn_os_unlock", use_container_width=True):
                db.unlock_os_settings()
                st.session_state.pop("os_inspection_data", None)
                st.info("Settings unlocked. Pod returned to Draft Mode.")
                st.rerun()

        with col_l2:
            if st.button("💥 Wipe Out & Reset OS1", key="btn_os_wipe_locked", use_container_width=True, type="primary", help="Safely closes broker legs, purges DB records for OS1, and unlocks settings."):
                res_w = wipe_out_and_reset_os_unit("OS1")
                st.session_state.pop("os_inspection_data", None)
                if res_w.get("ok"):
                    st.success(res_w.get("message"))
                else:
                    st.warning(res_w.get("message"))
                time.sleep(1)
                st.rerun()

        with col_l3:
            btn_fetch_locked = st.button("🔍 Fetch Live Candidate Prices & Decay Status", key="btn_fetch_locked", use_container_width=True)

        if btn_fetch_locked or "os_inspection_data" not in st.session_state:
            with st.spinner("Fetching live option chain quotes and yesterday benchmarks..."):
                st.session_state["os_inspection_data"] = inspect_os_candidates(
                    expiry_date=s_exp,
                    target_premium=s_tp,
                    manual_ce_strike=s_ce if s_mode == "MANUAL" else None,
                    manual_pe_strike=s_pe if s_mode == "MANUAL" else None,
                    hedge_dist=DEFAULT_HEDGE_DISTANCE
                )

        selected_exp = s_exp
        lots = s_lots
        user_lot_size = s_ls
        target_prem = s_tp
        m_ce = s_ce if s_mode == "MANUAL" else None
        m_pe = s_pe if s_mode == "MANUAL" else None

    else:
        # ---------------------------------------------------------------------
        # UNLOCKED DRAFT MODE (SYSTEM INERT & SAFE)
        # ---------------------------------------------------------------------
        st.markdown('''
        <div style="background: #1e1b10; border: 2px solid #f59e0b; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.2rem; font-weight: 800; color: #fbbf24;">
                        ⚠️ OS ENGINE IN UNLOCKED DRAFT MODE
                    </span>
                    <span style="background: #451a03; color: #fde68a; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; font-weight: 700; margin-left: 10px;">
                        NO TRADES ALLOWED
                    </span>
                    <div style="font-size: 0.90rem; color: #ffffff; margin-top: 6px; line-height: 1.5;">
                        The Option Selling engine is completely inert. Configure your Expiry, Lot Size, and Strike Mode below, preview candidate strikes, and click <b style="color: #fbbf24;">'🔒 Lock & Arm Pod Settings'</b> to activate.
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        st.markdown('<p class="section-title">🎛️ STEP 1: CONFIGURE & PREVIEW STRIKES (DRAFT)</p>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="block-card">', unsafe_allow_html=True)
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1.5, 2, 0.9, 1.1, 1.3])

            with col_h1:
                cur_hor = saved_cfg.get("horizon", "Weekly Expiry")
                horizon = st.radio("Expiry Horizon", ["Weekly Expiry", "Monthly Expiry"], index=0 if cur_hor == "Weekly Expiry" else 1, horizontal=True, key="os_tab_horizon")
                active_list = cat_expiries.get("weekly", []) if horizon == "Weekly Expiry" else cat_expiries.get("monthly", [])
                if not active_list:
                    active_list = all_expiries

            with col_h2:
                cur_exp = saved_cfg.get("expiry_date", "")
                exp_idx = active_list.index(cur_exp) if cur_exp in active_list else 0
                selected_exp = st.selectbox(f"Select {horizon} Date", active_list, index=exp_idx, key="os_tab_exp_date")

            with col_h3:
                lots = st.number_input("Lots", min_value=1, max_value=100, value=saved_cfg.get("lots", 1), step=1, key="os_tab_lots")

            with col_h4:
                current_db_ls = saved_cfg.get("lot_size", 65)
                user_lot_size = st.number_input(
                    "Lot Size (Manual)",
                    min_value=1,
                    max_value=5000,
                    value=current_db_ls,
                    step=5,
                    key="os_tab_lot_size",
                    help="User-decided manual contract lot size (e.g. 65, 75, 25, 50)"
                )

            with col_h5:
                target_prem = st.number_input("Target Premium (≤ ₹)", value=saved_cfg.get("target_premium", DEFAULT_TARGET_PREMIUM), step=10.0, format="%.1f", key="os_tab_tp_val")

            calc_qty = lots * user_lot_size
            st.markdown(f'''
            <div style="background: #0f172a; border: 1.5px solid #3b82f6; border-radius: 8px; padding: 10px 16px; margin: 8px 0 14px 0; font-size: 0.92rem; color: #ffffff; display: flex; justify-content: space-between; align-items: center;">
                <span>📦 <b style="color: #93c5fd;">Position Sizing:</b> {lots} Lot(s) &times; {user_lot_size} Qty/Lot</span>
                <span style="background: #1e3a8a; color: #bfdbfe; font-weight: 700; padding: 4px 12px; border-radius: 12px;">Total Order Qty: {calc_qty} units</span>
            </div>
            ''', unsafe_allow_html=True)

            col_adv1, col_adv2 = st.columns([2, 2])
            with col_adv1:
                cur_mode_idx = 0 if saved_cfg.get("mode", "AUTO") == "AUTO" else 1
                stk_mode = st.radio("Strike Hunter Mode", ["Auto Hunter (≤ ₹150 in 50-Ending Strikes)", "Manual Strike Override"], index=cur_mode_idx, horizontal=True, key="os_tab_stk_mode")

            m_ce = None
            m_pe = None
            with col_adv2:
                if stk_mode == "Manual Strike Override":
                    cm1, cm2 = st.columns(2)
                    live_spot = kite_executor.get_nifty_spot()
                    if live_spot <= 0:
                        live_spot = 23500.0
                    base_hundred = (int(live_spot) // 100) * 100
                    default_50_ce = base_hundred + 250
                    default_50_pe = base_hundred - 250
                    def_ce = saved_cfg.get("manual_ce") or default_50_ce
                    def_pe = saved_cfg.get("manual_pe") or default_50_pe
                    with cm1:
                        m_ce = st.number_input("Manual CE Strike", value=int(def_ce), step=50, key="os_tab_man_ce")
                    with cm2:
                        m_pe = st.number_input("Manual PE Strike", value=int(def_pe), step=50, key="os_tab_man_pe")

            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            btn_fetch = st.button("🔍 STEP 1: FETCH & PREVIEW LIVE STRIKES", key="btn_os_fetch_strikes", use_container_width=True, type="primary")

            if btn_fetch:
                with st.spinner("Fetching strikes..."):
                    st.session_state["os_inspection_data"] = inspect_os_candidates(
                        expiry_date=selected_exp,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        hedge_dist=DEFAULT_HEDGE_DISTANCE
                    )

            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # INSPECTION RESULTS DISPLAY (BOTH LOCKED & UNLOCKED)
    # -------------------------------------------------------------------------
    inspection = st.session_state.get("os_inspection_data")
    if inspection and inspection.get("ok"):
        h_ce = inspection.get("ce", {})
        h_pe = inspection.get("pe", {})

        col_ce_box, col_pe_box = st.columns(2)

        with col_ce_box:
            if h_ce.get("ok"):
                ce_dec = h_ce.get("is_decaying", False)
                ce_border = "#10b981" if ce_dec else "#ef4444"
                ce_badge = "🟢 DECAYING (QUALIFIED TO SELL)" if ce_dec else "🔴 EXPANDING (SKIP)"
                diff_sign = "-" if h_ce.get('decay_diff', 0) >= 0 else "+"

                st.markdown(f'''
                <div style="background: #0f172a; border: 2px solid {ce_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📞 CALL WING: {h_ce.get('sell_strike', '--')} CE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:{ce_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {ce_border};">{ce_badge}</span>
                    </div>
                    <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                        &bull; Today 3 PM LTP: <b style="color:#ffffff; font-size:1.05rem;">₹{h_ce.get('sell_ltp', 0.0):.2f}</b><br/>
                        &bull; Yesterday Reference Price: <b style="color:#cbd5e1;">₹{h_ce.get('yesterday_anchor', 0.0):.2f}</b><br/>
                        &bull; Momentum Decay: <b style="color:{ce_border}; font-size:1.05rem;">{diff_sign}₹{abs(h_ce.get('decay_diff', 0)):.2f}</b><br/>
                        &bull; 500-pt Hedge ("Helmet"): <b style="color:#60a5fa; font-weight:700;">{h_ce.get('hedge_strike', '--')} CE</b> (LTP: ₹{h_ce.get('hedge_ltp', 0.0):.2f})<br/>
                        &bull; 1.382 Stop Loss Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_ce.get('sl_price', 0.0):.2f}</b> (+{h_ce.get('sl_pct', 38.2)}%)
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div style="background: #1e1b10; border: 2px solid #ef4444; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#f87171;">📞 CALL WING: NOT AVAILABLE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:#ef4444; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid #ef4444;">🔴 UNQUALIFIED</span>
                    </div>
                    <div style="font-size:0.95rem; color:#cbd5e1; line-height:1.6;">
                        {h_ce.get('message', 'No eligible contracts found >= min floor Rs105.00.')}
                    </div>
                </div>
                ''', unsafe_allow_html=True)

        with col_pe_box:
            if h_pe.get("ok"):
                pe_dec = h_pe.get("is_decaying", False)
                pe_border = "#10b981" if pe_dec else "#ef4444"
                pe_badge = "🟢 DECAYING (QUALIFIED TO SELL)" if pe_dec else "🔴 EXPANDING (SKIP)"
                diff_sign_p = "-" if h_pe.get('decay_diff', 0) >= 0 else "+"

                st.markdown(f'''
                <div style="background: #0f172a; border: 2px solid {pe_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📉 PUT WING: {h_pe.get('sell_strike', '--')} PE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:{pe_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {pe_border};">{pe_badge}</span>
                    </div>
                    <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                        &bull; Today 3 PM LTP: <b style="color:#ffffff; font-size:1.05rem;">₹{h_pe.get('sell_ltp', 0.0):.2f}</b><br/>
                        &bull; Yesterday Reference Price: <b style="color:#cbd5e1;">₹{h_pe.get('yesterday_anchor', 0.0):.2f}</b><br/>
                        &bull; Momentum Decay: <b style="color:{pe_border}; font-size:1.05rem;">{diff_sign_p}₹{abs(h_pe.get('decay_diff', 0)):.2f}</b><br/>
                        &bull; 500-pt Hedge ("Helmet"): <b style="color:#60a5fa; font-weight:700;">{h_pe.get('hedge_strike', '--')} PE</b> (LTP: ₹{h_pe.get('hedge_ltp', 0.0):.2f})<br/>
                        &bull; 1.382 Stop Loss Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_pe.get('sl_price', 0.0):.2f}</b> (+{h_pe.get('sl_pct', 38.2)}%)
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div style="background: #1e1b10; border: 2px solid #ef4444; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#f87171;">📉 PUT WING: NOT AVAILABLE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:#ef4444; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid #ef4444;">🔴 UNQUALIFIED</span>
                    </div>
                    <div style="font-size:0.95rem; color:#cbd5e1; line-height:1.6;">
                        {h_pe.get('message', 'No eligible contracts found >= min floor Rs105.00.')}
                    </div>
                </div>
                ''', unsafe_allow_html=True)

        step_lbl = "🎯 50-Ending Series Mode (Zero-Clash Shield Active)"
        occ_cnt = len(inspection.get("occupied_strikes", []))
        shield_lbl = f"🛡️ Zero-Clash Shield Active ({occ_cnt} M-Unit strikes avoided)" if occ_cnt > 0 else "🛡️ Zero-Clash Shield Active"

        st.markdown(f'''
        <div style="background: #0f172a; border: 1.5px solid #ff5722; border-left: 6px solid #ff5722; padding: 14px 20px; border-radius: 8px; margin: 16px 0; color: #ffffff; font-size: 0.95rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; margin-bottom: 6px;">
                <b style="color: #ff8a65;">System Audit Result:</b>
                <div>
                    <span style="background: #1e3a8a; color: #93c5fd; font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; font-weight: 700; margin-right: 6px;">{step_lbl}</span>
                    <span style="background: #064e3b; color: #6ee7b7; font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; font-weight: 700;">{shield_lbl}</span>
                </div>
            </div>
            <span style="color: #ffffff; font-weight: 600;">{inspection['status_msg']}</span>
        </div>
        ''', unsafe_allow_html=True)

    elif inspection and not inspection.get("ok"):
        st.markdown(f'''
        <div style="background: #1e1b10; border: 1.5px solid #f59e0b; border-left: 6px solid #f59e0b; padding: 16px 20px; border-radius: 8px; margin: 16px 0; color: #ffffff;">
            <div style="font-size: 1.05rem; font-weight: 800; color: #fbbf24; margin-bottom: 6px;">⚠️ No Eligible Option Wings Found</div>
            <div style="font-size: 0.92rem; color: #cbd5e1; line-height: 1.5;">{inspection.get("status_msg", "Contracts did not meet the target premium floor or reference decay requirements.")}</div>
        </div>
        ''', unsafe_allow_html=True)

    # ── STEP 2: REVIEW & LOCK OS POD SETTINGS ─────────────────────────────
    st.markdown('<p class="section-title" style="margin-top:24px;">🔒 STEP 2: REVIEW & LOCK OS POD SETTINGS</p>', unsafe_allow_html=True)
    if not is_locked:
        st.markdown(
            '<div style="background: rgba(245, 158, 11, 0.12); border-left: 4px solid #f59e0b; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #fde68a; margin-bottom: 12px;">'
            '👉 <b>Step 1 Complete!</b> Review decaying candidate contracts above. Click below to lock settings and unlock Step 3 Execution options.'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("🔒 STEP 2: CONFIRM & LOCK OS POD SETTINGS", key="btn_os_lock_settings", use_container_width=True, type="primary"):
            db.set_os_settings(
                locked=True,
                horizon=horizon if 'horizon' in locals() else "Weekly Expiry",
                expiry_date=selected_exp,
                lots=lots,
                lot_size=user_lot_size,
                mode="MANUAL" if ('stk_mode' in locals() and stk_mode == "Manual Strike Override") else "AUTO",
                manual_ce=m_ce or 0,
                manual_pe=m_pe or 0,
                target_premium=target_prem
            )
            db.set_os_lot_size(user_lot_size)
            st.success("✅ Settings LOCKED! You can now proceed to Step 3.")
            st.rerun()
    else:
        st.markdown(
            '<div style="background: rgba(16, 185, 129, 0.12); border-left: 4px solid #10b981; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #a7f3d0; margin-bottom: 12px;">'
            '✅ <b>STEP 2 COMPLETE:</b> OS Pod Settings are LOCKED in database.'
            '</div>',
            unsafe_allow_html=True
        )

    # ── STEP 3: EXECUTION ROUTING ─────────────────────────────────────────
    st.markdown('<p class="section-title" style="margin-top:20px;">🚀 STEP 3: EXECUTE OR ARM OS POD</p>', unsafe_allow_html=True)

    pod_unit = st.selectbox("Assign to Pod Identifier", ["OS1", "OS2", "OS3", "OS4", "OS5"], index=0, key="os_tab_pod_select")
    auto_traded = db.has_os_auto_traded_today(pod_unit)

    col_ov1, col_ov2 = st.columns(2)
    with col_ov1:
        if auto_traded:
            st.info(f"🤖 <b>3:02 PM Auto-Trade:</b> Completed today for <b>{pod_unit}</b>. Manual trade execution remains available anytime.")
        elif is_locked:
            st.success(f"🔒 <b>{pod_unit} Settings:</b> LOCKED & ARMED for 15:02 IST auto-audit.")
        else:
            st.warning(f"📝 <b>{pod_unit} Settings:</b> In Draft Mode. Clicking either deploy button below will automatically LOCK & ARM these settings.")

    act_c1, act_c2 = st.columns(2)
    with act_c1:
        if st.button("🚀 Execute Qualified Decaying Trade(s) Now (Manual Deploy)", key="btn_exec_os_now", use_container_width=True, type="primary"):
            if not is_locked:
                db.set_os_settings(
                    locked=True,
                    horizon=horizon if 'horizon' in locals() else "Weekly Expiry",
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if ('stk_mode' in locals() and stk_mode == "Manual Strike Override") else "AUTO",
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                db.set_os_lot_size(user_lot_size)
            with st.spinner("Placing hedge order FIRST on broker, then selling short leg..."):
                res = deploy_os_unit(
                    unit_name=pod_unit,
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    target_premium=target_prem,
                    manual_ce_strike=m_ce,
                    manual_pe_strike=m_pe,
                    deploy_now=True,
                    force_override_daily_limit=True,
                    is_manual=True
                )
                if res.get("ok"):
                    st.success(res.get("message"))
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(res.get("message"))

    with act_c2:
        if st.button("⏱️ Arm for 3:00 PM Auto-Audit Only", key="btn_arm_os_3pm", use_container_width=True):
            if not is_locked:
                db.set_os_settings(
                    locked=True,
                    horizon=horizon if 'horizon' in locals() else "Weekly Expiry",
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if ('stk_mode' in locals() and stk_mode == "Manual Strike Override") else "AUTO",
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                db.set_os_lot_size(user_lot_size)
            res = deploy_os_unit(
                unit_name=pod_unit,
                expiry_date=selected_exp,
                lots=lots,
                lot_size=user_lot_size,
                target_premium=target_prem,
                manual_ce_strike=m_ce,
                manual_pe_strike=m_pe,
                deploy_now=False,
                is_manual=False
            )
            if res.get("ok"):
                st.info(f"Unit {pod_unit} armed in PENDING. Engine will audit decay at 15:02 IST and execute qualified wings.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(res.get("message"))

    st.markdown("<br/>", unsafe_allow_html=True)

    # 3. ACTIVE OS PODS COCKPIT
    st.markdown('<p class="section-title">📦 ACTIVE OS PODS (OPTION SELLING UNITS)</p>', unsafe_allow_html=True)

    block_pnls = portfolio.get("block_pnls", [])
    os_pnls = [bp for bp in block_pnls if (bp["block"].get("anchor_unit_name") or "").strip().upper().startswith("OS")]

    if not os_pnls:
        st.markdown("""
        <div style="text-align:center;padding:40px 0;color:#64748b;">
            <div style="font-size:2.5rem;">🎯</div>
            <div style="font-size:1.05rem;font-weight:600;margin-top:8px;">No Active OS Pods Running</div>
            <div style="font-size:0.80rem;margin-top:4px;">Fetch strikes and deploy an OS pod using the console above.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for bp in os_pnls:
            b = bp["block"]
            unit_id = (b.get("anchor_unit_name") or f"OS{b['block_number']}").strip().upper()
            total_pnl = bp["total_pnl"]
            pnl_color = "#166534" if total_pnl >= 0 else "#991b1b"
            pnl_sign = "+" if total_pnl >= 0 else ""

            st.markdown(f"""
            <div class="block-card" style="border-left: 4px solid #ff5722; margin-bottom: 16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div>
                        <span style="font-size:1.15rem; font-weight:700; color:#0f172a;">Pod {unit_id} (Block #{b['block_number']})</span>
                        <span style="margin-left:8px; font-size:0.75rem; background:#fff3e0; color:#e65100; padding:2px 8px; border-radius:12px; font-weight:600;">
                            Expiry: {b.get('expiry_date')}
                        </span>
                    </div>
                    <div style="font-size:1.25rem; font-weight:700; font-family:monospace; color:{pnl_color};">
                        {pnl_sign}₹{total_pnl:,.2f}
                    </div>
                </div>
            """, unsafe_allow_html=True)

            s_pnls = bp.get("strike_pnls", [])
            if s_pnls:
                rows = []
                for sp in s_pnls:
                    leg = sp.get("leg_type")
                    opt = sp.get("option_type")
                    stk = sp.get("strike_price")
                    anc = sp.get("anchor_price", 0.0)
                    ltp = sp.get("ltp", 0.0)
                    pnl = sp.get("pnl", 0.0)
                    stat = sp.get("status")
                    sl_p = float(sp.get("sl_price") or (anc * DEFAULT_SL_MULTIPLIER if leg == "SELL" and anc > 0 else 0.0))
                    decay_str = f"{((anc - ltp) / anc * 100):.1f}%" if leg == "SELL" and anc > 0 and ltp > 0 else "--"

                    rows.append({
                        "Leg": f"{'📉 SELL' if leg == 'SELL' else '🛡️ HEDGE'}",
                        "Strike": f"{stk} {opt}",
                        "Entry Price": f"₹{anc:.2f}",
                        "LTP": f"₹{ltp:.2f}" if ltp > 0 else "--",
                        "Stop Loss (1.382)": f"₹{sl_p:.2f}" if leg == "SELL" and sl_p > 0 else "--",
                        "Theta Decay": decay_str,
                        "Lots": sp.get("lots"),
                        "P&L": f"{'+' if pnl >= 0 else ''}₹{pnl:,.2f}",
                        "Status": stat
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            act_c1, act_c2, act_c3 = st.columns([1, 1, 2])
            with act_c1:
                if st.button("💰 Lock Hedge Profit", key=f"btn_lock_h_{b['block_id']}", use_container_width=True):
                    hedges = [s for s in db.get_strikes_by_block(b["block_id"], status_filter="OPEN") if s["leg_type"] == "HEDGE_BUY"]
                    for h in hedges:
                        bm.close_hedge_strike_now(h["strike_id"])
                    st.success("Hedge profits locked!")
                    st.rerun()
            with act_c2:
                if st.button("🛑 Square Off Pod", key=f"btn_sqoff_{b['block_id']}", use_container_width=True):
                    bm.kill_block(b["block_id"])
                    st.warning(f"Pod {unit_id} squared off!")
                    st.rerun()
            with act_c3:
                if st.button("🔄 Reset Daily Trade Flag", key=f"btn_reset_d_{b['block_id']}", use_container_width=True, help="Resets today's trade flag allowing another trade in this pod."):
                    db.reset_os_daily_trade_flag(unit_id)
                    st.success(f"Daily trade flag reset for {unit_id}.")
                    st.rerun()

            # 1-Click OS Wipe Out & Clean Slate Reset Button
            st.markdown("<div style='margin-top:8px;'>", unsafe_allow_html=True)
            if st.button(f"💥 Wipe Out & Reset {unit_id} (Clean Slate)", key=f"btn_wipe_reset_os_{b['block_id']}", use_container_width=True, type="primary", help=f"Safely closes active legs on Kite broker, purges DB records for {unit_id}, and returns system to clean Draft Mode."):
                res_w = wipe_out_and_reset_os_unit(unit_id)
                st.session_state.pop("os_inspection_data", None)
                if res_w.get("ok"):
                    st.success(res_w.get("message"))
                else:
                    st.warning(res_w.get("message"))
                time.sleep(1)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)
