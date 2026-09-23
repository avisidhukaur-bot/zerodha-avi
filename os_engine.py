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
from typing import Optional, Dict, Any, List, Tuple, Union, Set
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

def get_yesterday_reference_price(trading_symbol: str, symbol_token: str = "") -> float:
    """
    Fetches the verified yesterday reference price for an option contract:
      1. Checks SQLite setting (specifically saved 3:00 PM price).
      2. If not recorded in SQLite, queries Kite quote API for exchange previous close:
         kite.quote(["NFO:TRADINGSYMBOL"])["ohlc"]["close"]
    """
    # 1. Check local anchor
    anchor = db.get_os_strike_anchor(trading_symbol)
    if anchor > 0.0:
        return anchor

    # 2. Query live quote from Kite for official previous close
    if kite_executor.ensure_logged_in():
        try:
            query = f"NFO:{trading_symbol}"
            res = kite_executor.kite.quote([query])
            if query in res:
                ohlc = res[query].get("ohlc", {})
                prev_close = float(ohlc.get("close", 0.0) or 0.0)
                if prev_close > 0.0:
                    set_option_anchor(trading_symbol, prev_close)
                    return prev_close
        except Exception as e:
            _log(f"Quote previous close lookup failed for {trading_symbol}: {e}", "WARN")

    return 0.0


def set_option_anchor(trading_symbol: str, price: float) -> None:
    """Saves yesterday's 3:00 PM anchor price for this specific option symbol."""
    db.set_os_strike_anchor(trading_symbol, price)
    _log(f"Anchor updated for {trading_symbol}: Rs{price:.2f}", "ANCHOR")


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


# ─────────────────────────────────────────────────────────────────────────────
# ANTI-COLLISION SHIELD & DYNAMIC STEP HUNTER (100 vs 500 MULTIPLES)
# ─────────────────────────────────────────────────────────────────────────────

def is_far_month_expiry(expiry_date: str) -> bool:
    """
    Determines if an expiry belongs to a Far Month (Next Month / Deep Monthly).
    Near Month (Current Month) => 100-pt steps.
    Far Month (Next Month+)   => 500-pt steps (to eliminate illiquid ghost strikes).
    """
    try:
        today = datetime.now(IST).date()
        exp_dt = None
        for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
            try:
                exp_dt = datetime.strptime(str(expiry_date).strip(), fmt).date()
                break
            except ValueError:
                pass
        if exp_dt:
            # If expiry is in a future calendar month or more than 35 days away
            if (exp_dt.year > today.year) or (exp_dt.year == today.year and exp_dt.month > today.month):
                return True
            days_away = (exp_dt - today).days
            return days_away > 35
    except Exception as e:
        _log(f"Error checking far-month expiry: {e}", "WARN")
    return False


def get_os_step_size(expiry_date: str, override_step: Union[int, str] = "AUTO") -> int:
    """
    Resolves the strike step size:
      - Near Month: 100 Multiples (Abundant liquidity on every 100 strike).
      - Far Month : 500 Multiples (Guaranteed market maker liquidity on 23000, 23500, 24000, 24500...).
    """
    step_str = str(override_step).strip().upper()
    if step_str in ("100", "STRICT 100"):
        return 100
    if step_str in ("500", "STRICT 500"):
        return 500
    # Auto resolution based on expiry horizon
    return 500 if is_far_month_expiry(expiry_date) else 100


def get_occupied_strikes(expiry_date: str) -> Set[Tuple[int, str]]:
    """
    ZERO-CLASH STRIKE SHIELD:
    Returns all active/open (strike_price, option_type) currently held by:
      1. M-Series Units (M1, M2, M3...) in SQLite DB for this expiry.
      2. Other active blocks in SQLite DB for this expiry.
      3. Live broker open net positions (from Kite).
    """
    occupied: Set[Tuple[int, str]] = set()

    # 1. Normalize target expiry
    exp_norm = str(expiry_date).strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            exp_norm = datetime.strptime(exp_norm, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            pass

    # 2. Query SQLite DB active blocks and open strikes
    try:
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        for b in active_blocks:
            b_exp = str(b.get("expiry_date", "")).strip()
            b_exp_norm = b_exp
            for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    b_exp_norm = datetime.strptime(b_exp, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    pass

            if b_exp_norm == exp_norm or not b_exp:
                strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
                for s in strikes:
                    if s.get("leg_type") == "SELL":
                        try:
                            occupied.add((int(float(s["strike_price"])), str(s["option_type"]).strip().upper()))
                        except Exception:
                            pass
    except Exception as e:
        _log(f"Error querying occupied DB strikes: {e}", "WARN")

    # 3. Query live broker net positions
    try:
        positions = kite_executor.get_positions()
        for p in positions:
            if p.get("quantity", 0) != 0:
                tsym = str(p.get("tradingsymbol", "")).strip().upper()
                if "NIFTY" in tsym and (tsym.endswith("CE") or tsym.endswith("PE")):
                    opt_t = "CE" if tsym.endswith("CE") else "PE"
                    # Extract strike number (digits before CE/PE)
                    digits = ""
                    for ch in reversed(tsym[:-2]):
                        if ch.isdigit():
                            digits = ch + digits
                        else:
                            break
                    if digits and len(digits) >= 4:
                        occupied.add((int(digits), opt_t))
    except Exception as e:
        _log(f"Error querying occupied broker positions: {e}", "WARN")

    return occupied


def hunt_os_strike(
    option_type: str,
    expiry_date: str,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER,
    step_size: Union[int, str] = "AUTO"
) -> Dict[str, Any]:
    """
    Hunts candidate option contract with:
      - Dynamic Step Selection: 100 Multiples (Near Month) vs 500 Multiples (Far Month).
      - Zero-Clash Strike Shield: Automatically shifts (+1/-1 step) if strike is already active in M-units/broker.
      - Far-Month Premium Flexibility: Allows rich premiums up to ₹185 on 500-multiples.
      - 500-pt OTM Hedge ("Helmet Rule").
      - 1.382 Stop Loss calculation (+38.2%).
    """
    opt_type = option_type.strip().upper()
    if opt_type not in ("CE", "PE"):
        return {"ok": False, "message": f"Invalid option type: {option_type}. Must be CE or PE."}

    df = kite_executor._load_security_master()
    if df.empty:
        return {"ok": False, "message": "Security master is empty. Cannot scan option chain."}

    # Normalize expiry string to YYYY-MM-DD
    exp_yyyy_mm_dd = str(expiry_date).strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            exp_yyyy_mm_dd = datetime.strptime(exp_yyyy_mm_dd, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    subset = df[
        (df["name"].str.upper() == "NIFTY") &
        (df["exchange"].str.upper() == "NFO") &
        (df["expiry"] == exp_yyyy_mm_dd) &
        (df["instrument_type"].str.upper() == opt_type)
    ]

    if subset.empty:
        return {"ok": False, "message": f"No NIFTY {opt_type} contracts found for expiry {exp_yyyy_mm_dd}."}

    # Resolve step size (100 for near month, 500 for far month)
    step = get_os_step_size(exp_yyyy_mm_dd, step_size)
    is_far_m = is_far_month_expiry(exp_yyyy_mm_dd)

    # Far-Month Premium Flexibility: Allow higher premium up to ₹185 on 500-multiples
    effective_target_premium = float(target_premium)
    if is_far_m and step == 500 and effective_target_premium <= 150.0:
        effective_target_premium = 185.0

    occupied_set = get_occupied_strikes(exp_yyyy_mm_dd)

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
        collision_shifted = False
        original_strike = sell_strike
    else:
        # 2. AUTO HUNTER: ODD STRIKE PARITY & DYNAMIC STEP SELECTION
        # Rule: OS System trades strictly ODD Strike Multiples (e.g., 23100, 23300, 23500, 23700, 23900...)
        odd_subset = subset[(subset["strike"] // 100) % 2 != 0].copy()
        if not odd_subset.empty:
            mult_subset = odd_subset
        else:
            mult_subset = subset[subset["strike"] % step == 0].copy()
            if mult_subset.empty:
                return {"ok": False, "message": f"No {step}-multiple strikes available for this expiry."}

        live_spot = kite_executor.get_nifty_spot()
        if live_spot > 0:
            if opt_type == "CE":
                candidates = mult_subset[(mult_subset["strike"] >= live_spot - 300) & (mult_subset["strike"] <= live_spot + 3500)]
            else:
                candidates = mult_subset[(mult_subset["strike"] <= live_spot + 300) & (mult_subset["strike"] >= live_spot - 3500)]
            if candidates.empty:
                candidates = mult_subset
        else:
            candidates = mult_subset

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

        # Find best candidate closest to target premium (~₹150)
        under_target = [c for c in scored_candidates if c["ltp"] <= effective_target_premium]
        if under_target:
            selected = max(under_target, key=lambda x: x["ltp"])
        else:
            selected = min(scored_candidates, key=lambda x: x["ltp"])

        raw_strike = selected["strike"]
        original_strike = raw_strike
        collision_shifted = False

        # ── ZERO-CLASH STRIKE SHIELD (ANTI-COLLISION GATEKEEPER WITH ODD PARITY) ──
        # Shift +200 for CE (Up) or -200 for PE (Down) to avoid clash while keeping ODD parity!
        curr_candidate_strike = raw_strike
        shift_step = 200 if step == 100 else 500
        max_shifts = 6
        shift_count = 0
        while (curr_candidate_strike, opt_type) in occupied_set and shift_count < max_shifts:
            collision_shifted = True
            shift_count += 1
            if opt_type == "CE":
                curr_candidate_strike += shift_step
            else:
                curr_candidate_strike -= shift_step
            _log(f"[ANTI-COLLISION] {opt_type} Strike {curr_candidate_strike - (shift_step if opt_type == 'CE' else -shift_step)} occupied! Shifting to {curr_candidate_strike}...", "WARN")

        # Resolve details for the chosen (unoccupied) strike
        chosen_row = subset[subset["strike"] == float(curr_candidate_strike)]
        if not chosen_row.empty:
            chosen_item = chosen_row.iloc[0]
            sell_strike = curr_candidate_strike
            sell_token = str(chosen_item["instrument_token"])
            sell_tsymbol = str(chosen_item["tradingsymbol"])
            sell_ltp = ltp_dict.get(sell_tsymbol, 0.0)
            if sell_ltp <= 0.0:
                sell_ltp = kite_executor.get_ltp(sell_token, sell_tsymbol)
        else:
            # Fallback if stepped beyond subset range
            sell_strike = selected["strike"]
            sell_token = selected["token"]
            sell_tsymbol = selected["tradingsymbol"]
            sell_ltp = selected["ltp"]

    # 3. 500-POINT OTM HEDGE RESOLUTION ("Helmet Rule")
    # For 500-step (far month) or 100-step, standard hedge distance is 500 pts
    actual_hedge_dist = max(hedge_dist, step) if step == 500 else hedge_dist
    if opt_type == "CE":
        hedge_strike = sell_strike + actual_hedge_dist
    else:
        hedge_strike = sell_strike - actual_hedge_dist

    # Anti-collision check for hedge strike as well
    if (hedge_strike, opt_type) in occupied_set:
        hedge_shift = 200 if step == 100 else 500
        hedge_strike = hedge_strike + hedge_shift if opt_type == "CE" else hedge_strike - hedge_shift

    hedge_row = subset[subset["strike"] == float(hedge_strike)]
    if hedge_row.empty:
        hedge_candidates = subset[subset["strike"] > sell_strike] if opt_type == "CE" else subset[subset["strike"] < sell_strike]
        if not hedge_candidates.empty:
            hedge_row = hedge_candidates.iloc[-1:] if opt_type == "CE" else hedge_candidates.iloc[:1]
        else:
            return {"ok": False, "message": f"Could not find OTM hedge strike {hedge_strike} {opt_type}."}

    hedge_item = hedge_row.iloc[0]
    hedge_strike_actual = int(hedge_item["strike"])
    hedge_token = str(hedge_item["instrument_token"])
    hedge_tsymbol = str(hedge_item["tradingsymbol"])
    hedge_ltp = kite_executor.get_ltp(hedge_token, hedge_tsymbol)

    # 4. YESTERDAY REFERENCE PRICE & OPTION DECAY EVALUATION
    yesterday_anchor = get_yesterday_reference_price(sell_tsymbol, sell_token)
    if yesterday_anchor <= 0.0:
        yesterday_anchor = sell_ltp
        set_option_anchor(sell_tsymbol, sell_ltp)

    is_decaying = (sell_ltp < yesterday_anchor) if yesterday_anchor > 0 else True
    decay_diff = yesterday_anchor - sell_ltp

    # 5. 1.382 STOP LOSS CALCULATION
    sl_base = sell_ltp if sell_ltp > 0 else effective_target_premium
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
        "target_premium": effective_target_premium,
        "step_size": step,
        "is_far_month": is_far_m,
        "collision_shifted": collision_shifted,
        "original_strike": original_strike,
        "occupied_strikes_count": len(occupied_set)
    }


def inspect_os_candidates(
    expiry_date: str,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_ce_strike: Optional[int] = None,
    manual_pe_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER,
    step_size: Union[int, str] = "AUTO"
) -> Dict[str, Any]:
    """
    Step 1 Inspection Function:
    Fetches both Call and Put candidates for the chosen expiry,
    audits their yesterday reference price, and determines overall qualification.
    """
    hunt_ce = hunt_os_strike("CE", expiry_date, target_premium, manual_ce_strike, hedge_dist, sl_multiplier, step_size=step_size)
    hunt_pe = hunt_os_strike("PE", expiry_date, target_premium, manual_pe_strike, hedge_dist, sl_multiplier, step_size=step_size)

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
        "status_msg": status_msg
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
        "ok": True,
        "sell_strike_id": s_id,
        "hedge_strike_id": h_id,
        "message": exec_msg
    }


def deploy_os_unit(
    unit_name: str = "OS1",
    expiry_date: str = "",
    lots: int = 1,
    lot_size: Optional[int] = None,
    target_premium: float = DEFAULT_TARGET_PREMIUM,
    manual_ce_strike: Optional[int] = None,
    manual_pe_strike: Optional[int] = None,
    hedge_dist: int = DEFAULT_HEDGE_DISTANCE,
    sl_multiplier: float = DEFAULT_SL_MULTIPLIER,
    deploy_now: bool = True,
    force_override_daily_limit: bool = False,
    step_size: Union[int, str] = "AUTO"
) -> Dict[str, Any]:
    """
    Deploys qualified decaying OS wings:
      - Lot size is manually decided by user.
      - Enforces 'Din mein sirf ek hi baar trade karna hai'.
      - Deploys only qualified decaying wings (or manual overrides).
      - Long hedge is bought FIRST on broker terminal.
      - Zero-Clash Strike Shield & Dynamic Step Selection enabled.
    """
    unit_name = str(unit_name).strip().upper()
    if not unit_name.startswith("OS"):
        unit_name = f"OS_{unit_name}"

    # Manual user lot size persistence
    if lot_size and int(lot_size) > 0:
        db.set_os_lot_size(int(lot_size))
        _log(f"Manual lot size set to {lot_size} units per lot by operator.", "CONFIG")

    effective_lot_size = db.get_os_lot_size()
    total_qty = lots * effective_lot_size

    # Enforce daily 1-trade limit
    if deploy_now and not force_override_daily_limit:
        if db.has_os_traded_today(unit_name):
            msg = f"BLOCKED: Din mein sirf ek hi baar trade karna hai. Unit {unit_name} has already executed a trade today!"
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
        sl_multiplier=sl_multiplier,
        step_size=step_size
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

    deployed_actions = []

    if inspection["ce_qualified"]:
        res_ce = deploy_os_wing(block_id, hunt_ce, lots=lots, deploy_now=deploy_now)
        if res_ce.get("ok"):
            deployed_actions.append(f"Sold {hunt_ce['sell_strike']} CE (Hedge: {hunt_ce['hedge_strike']} CE)")

    if inspection["pe_qualified"]:
        res_pe = deploy_os_wing(block_id, hunt_pe, lots=lots, deploy_now=deploy_now)
        if res_pe.get("ok"):
            deployed_actions.append(f"Sold {hunt_pe['sell_strike']} PE (Hedge: {hunt_pe['hedge_strike']} PE)")

    summary_msg = " | ".join(deployed_actions)

    # Mark daily trade taken
    if deploy_now:
        db.mark_os_traded_today(unit_name)

    try:
        tg.send(
            f"🎯 <b>OS ENGINE DEPLOYMENT — {unit_name}</b> 🎯\n"
            f"Expiry: {expiry_date}\n"
            f"Action: <b>{summary_msg}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Lots</b>: {lots} lot(s)\n"
            f"<b>Manual Lot Size</b>: {effective_lot_size} Qty/Lot\n"
            f"<b>Total Traded Qty</b>: {total_qty} units\n"
            f"<b>Stop Loss Rule</b>: 1.382x Entry (+38.2%)\n"
            f"<b>Daily Status</b>: Today's trade locked (1 trade/day rule active)."
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
# OS POD COMPLETE WIPEOUT & RESET (1-Click Operator Reset for Next Month)
# ─────────────────────────────────────────────────────────────────────────────

def wipeout_os_unit_now(unit_name: str = "OS1", sync_live: bool = True) -> Dict[str, Any]:
    """
    1-Click Operator Action:
    Completely squares off any open live broker positions for the OS unit,
    purges/deletes the block and strikes from SQLite DB,
    and resets the daily trade flag and locked settings so the user can deploy fresh for next month.
    """
    clean_u = (unit_name or "OS1").strip().upper()
    _log(f"[OS-WIPEOUT] Starting complete wipeout for unit {clean_u} (sync_live={sync_live})...", "ALERT")

    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    target_blocks = [b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == clean_u]

    closed_orders = []

    if sync_live:
        for b in target_blocks:
            bid = b["block_id"]
            strikes = db.get_strikes_by_block(bid, status_filter="OPEN")

            sell_strikes = [s for s in strikes if s.get("leg_type") == "SELL"]
            hedge_strikes = [s for s in strikes if s.get("leg_type") == "HEDGE_BUY"]

            for s in sell_strikes + hedge_strikes:
                try:
                    res = bm.close_strike(s["strike_id"], close_hedge=False)
                    if res.get("ok"):
                        closed_orders.append(f"{s['strike_price']} {s['option_type']}")
                except Exception as e:
                    _log(f"[OS-WIPEOUT] Error closing strike {s['strike_id']}: {e}", "ERROR")

    # Wipe database records and reset settings
    db.wipeout_os_pod(clean_u)

    # Send Telegram Notification
    try:
        tg_msg = (
            f"💥 <b>OS POD WIPED OUT & RESET</b> 💥\n"
            f"Unit: <b>{clean_u}</b>\n"
            f"Closed Positions: <b>{', '.join(closed_orders) if closed_orders else 'None (Clean DB Wipe)'}</b>\n"
            f"Status: <b>Purged from Database & Ready for Next Month Deployment</b>"
        )
        tg.send(tg_msg)
    except Exception as e:
        _log(f"[OS-WIPEOUT] Telegram alert error: {e}", "WARN")

    return {
        "ok": True,
        "message": f"Unit {clean_u} has been completely wiped out and reset. You can now deploy a fresh contract for next month."
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3:00 PM OPTION SELLING LINE AUDIT & CONTINUATION (15:01 – 15:04 IST)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_os_3pm_decision() -> Dict[str, Any]:
    """
    Evaluates running trades and candidate options at 15:01 - 15:04 IST (Staggered after M-series 14:57-15:00):
      1. Running Trades:
         - Today 3 PM LTP < Yesterday Reference Price => CONTINUATION (Hold for Day 2, 3, 4).
         - Today 3 PM LTP >= Yesterday Reference Price => AUTO-CLOSE (Cut above line).
      2. Rolls over today's 3 PM price as tomorrow's anchor.
    """
    _log("⏰ 15:01 IST: Running 3:01 PM OS Option Selling Line Audit (Staggered Window)...", "DECISION")

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

                if ltp < yest_anchor:
                    # CONTINUATION
                    db.update_strike_trade_state(s_id, "CONTINUED")
                    _log(f"{unit_name}: {stk} {opt} SELL CONTINUED overnight (LTP Rs{ltp:.2f} < Line Rs{yest_anchor:.2f}).", "OK")
                    results.append(f"• <b>{unit_name}</b>: CONTINUED {stk} {opt} (LTP Rs{ltp:.2f} &lt; Line Rs{yest_anchor:.2f})")
                else:
                    # AUTO-CLOSE (Cut above line)
                    _log(f"{unit_name}: 🛑 LINE CUT! {stk} {opt} SELL rose above 3:00 PM line (LTP Rs{ltp:.2f} >= Rs{yest_anchor:.2f}). Auto-closing...", "EXIT")
                    bm.close_strike(s_id, close_hedge=True)
                    db.update_strike_trade_state(s_id, "CLOSED")
                    h_id = s.get("hedge_strike_id")
                    if h_id:
                        db.update_strike_trade_state(h_id, "CLOSED")

                    results.append(f"• <b>{unit_name}</b>: 🛑 AUTO-CLOSED {stk} {opt} + Hedge (LTP Rs{ltp:.2f} &ge; Line Rs{yest_anchor:.2f})")

                if ltp > 0:
                    set_option_anchor(tsym, ltp)

    try:
        text = "\n".join(results) if results else "• No active OS pods with running positions."
        tg.send(
            f"⏰ <b>15:01 IST OPTION SELLING LINE AUDIT</b> ⏰\n"
            f"Option Decay Evaluation Complete:\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{text}"
        )
    except Exception as e:
        _log(f"Error sending 3PM TG alert: {e}", "WARN")

    return {"ok": True, "results": results}



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
                    🎯 PURE OPTION MOMENTUM COCKPIT (OS1 SYSTEM)
                </span>
                <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 4px;">
                    Operator 2-Step Workflow &bull; 15:01–15:04 Staggered Audit &bull; ODD Strike Parity (~₹150 Prem) &bull; 500-pt Hedge &bull; 1.382 SL Rule
                </div>
            </div>
            <div style="margin-top: 8px;">
                <span style="background: rgba(255, 87, 34, 0.2); border: 1px solid #ff5722; color: #ff8a65; font-size: 0.75rem; padding: 4px 12px; border-radius: 20px; font-weight: 600;">
                    MAX 1 TRADE / DAY ACTIVE
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
        s_step = saved_cfg.get("step_size", "AUTO")
        s_ce = saved_cfg.get("manual_ce", 0)
        s_pe = saved_cfg.get("manual_pe", 0)
        s_tp = saved_cfg.get("target_premium", 150.0)
        s_locked_at = saved_cfg.get("locked_at", "")

        mode_badge = f"🎯 Manual Strikes ({s_ce} CE / {s_pe} PE)" if s_mode == "MANUAL" else f"🏹 Auto Hunter (&le; ₹{s_tp:.1f})"
        step_badge = "Auto (Near=100, Far=500)" if s_step == "AUTO" else f"{s_step} Multiples"

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
                <div>🛡️ <b style="color: #93c5fd;">Strike Grid:</b> <span style="color: #38bdf8; font-weight: 700;">{step_badge} (Zero-Clash Shield Active)</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        col_l1, col_l2 = st.columns([1, 3])
        with col_l1:
            if st.button("🔓 Unlock to Edit Settings", key="btn_os_unlock", use_container_width=True):
                db.unlock_os_settings()
                st.session_state.pop("os_inspection_data", None)
                st.info("Settings unlocked. Pod returned to Draft Mode.")
                st.rerun()

        with col_l2:
            btn_fetch_locked = st.button("🔍 Fetch Live Candidate Prices & Decay Status", key="btn_fetch_locked", use_container_width=True)

        if btn_fetch_locked or "os_inspection_data" not in st.session_state:
            with st.spinner("Fetching live option chain quotes and yesterday benchmarks..."):
                st.session_state["os_inspection_data"] = inspect_os_candidates(
                    expiry_date=s_exp,
                    target_premium=s_tp,
                    manual_ce_strike=s_ce if s_mode == "MANUAL" else None,
                    manual_pe_strike=s_pe if s_mode == "MANUAL" else None,
                    hedge_dist=DEFAULT_HEDGE_DISTANCE,
                    step_size=s_step
                )

        selected_exp = s_exp
        lots = s_lots
        user_lot_size = s_ls
        target_prem = s_tp
        selected_step = s_step
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
                        The Option Selling engine is completely inert. Configure your Expiry, Lot Size, Step Grid, and Strike Mode below, preview candidate strikes, and click <b style="color: #fbbf24;">'🔒 Lock & Arm Pod Settings'</b> to activate.
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

            col_adv1, col_adv2, col_adv3 = st.columns([1.5, 1.2, 1.3])
            with col_adv1:
                cur_mode_idx = 0 if saved_cfg.get("mode", "AUTO") == "AUTO" else 1
                stk_mode = st.radio("Strike Hunter Mode", ["Auto Hunter", "Manual Strike Override"], index=cur_mode_idx, horizontal=True, key="os_tab_stk_mode")

            with col_adv2:
                cur_step_val = saved_cfg.get("step_size", "AUTO")
                step_idx = 0 if cur_step_val == "AUTO" else (1 if cur_step_val in ("100", 100) else 2)
                step_ui = st.selectbox("Strike Multiples Grid", ["AUTO (Near=100, Far=500)", "Strict 100 Multiples", "Strict 500 Multiples"], index=step_idx, key="os_tab_step_ui")
                if "100" in step_ui and "AUTO" not in step_ui:
                    selected_step = "100"
                elif "500" in step_ui and "AUTO" not in step_ui:
                    selected_step = "500"
                else:
                    selected_step = "AUTO"

            m_ce = None
            m_pe = None
            with col_adv3:
                if stk_mode == "Manual Strike Override":
                    cm1, cm2 = st.columns(2)
                    with cm1:
                        def_ce = saved_cfg.get("manual_ce") or 23500
                        m_ce = st.number_input("Manual CE Strike", value=int(def_ce), step=100, key="os_tab_man_ce")
                    with cm2:
                        def_pe = saved_cfg.get("manual_pe") or 23100
                        m_pe = st.number_input("Manual PE Strike", value=int(def_pe), step=100, key="os_tab_man_pe")
                else:
                    st.markdown("""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 12px; margin-top:24px; font-size:0.80rem; color:#94a3b8;">
                        🛡️ <b>Anti-Collision:</b> Auto-shifts +1/-1 step if strike is active in M-units or broker.
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                btn_fetch = st.button("🔍 Fetch & Preview Strikes", key="btn_os_fetch_strikes", use_container_width=True)
            with col_b2:
                btn_lock = st.button("🔒 Lock & Arm Pod Settings", key="btn_os_lock_settings", use_container_width=True)

            if btn_fetch:
                with st.spinner("Fetching strikes..."):
                    st.session_state["os_inspection_data"] = inspect_os_candidates(
                        expiry_date=selected_exp,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        hedge_dist=DEFAULT_HEDGE_DISTANCE,
                        step_size=selected_step
                    )

            if btn_lock:
                db.set_os_settings(
                    locked=True,
                    horizon=horizon,
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if stk_mode == "Manual Strike Override" else "AUTO",
                    step_size=selected_step,
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                db.set_os_lot_size(user_lot_size)
                st.success("✅ Settings LOCKED & ARMED! System is now active.")
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # INSPECTION RESULTS DISPLAY (BOTH LOCKED & UNLOCKED)
    # -------------------------------------------------------------------------
    inspection = st.session_state.get("os_inspection_data")
    if inspection and inspection.get("ok"):
        h_ce = inspection["ce"]
        h_pe = inspection["pe"]

        col_ce_box, col_pe_box = st.columns(2)

        with col_ce_box:
            ce_dec = h_ce.get("is_decaying", False)
            ce_border = "#10b981" if ce_dec else "#ef4444"
            ce_badge = "🟢 DECAYING (QUALIFIED TO SELL)" if ce_dec else "🔴 EXPANDING (SKIP)"
            diff_sign = "-" if h_ce['decay_diff'] >= 0 else "+"
            ce_far = h_ce.get('is_far_month', False)
            ce_step = h_ce.get('step_size', 100)
            ce_shift = h_ce.get('collision_shifted', False)
            ce_orig = h_ce.get('original_strike', h_ce['sell_strike'])
            ce_shield_html = f"&bull; 🛡️ Anti-Collision: <b style='color:#38bdf8;'>Shifted from {ce_orig} CE (Occupied) ➔ {h_ce['sell_strike']} CE (+{ce_step} pts)</b><br/>" if ce_shift else "&bull; 🛡️ Anti-Collision: <b style='color:#34d399;'>Safe (0 Clash with M-Units/Broker)</b><br/>"

            st.markdown(f'''
            <div style="background: #0f172a; border: 2px solid {ce_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                    <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📞 CALL WING: {h_ce['sell_strike']} CE</span>
                    <span style="font-size:0.80rem; font-weight:800; color:{ce_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {ce_border};">{ce_badge}</span>
                </div>
                <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                    &bull; Today 3 PM LTP: <b style="color:#ffffff; font-size:1.05rem;">₹{h_ce['sell_ltp']:.2f}</b><br/>
                    &bull; Yesterday Reference Price: <b style="color:#cbd5e1;">₹{h_ce['yesterday_anchor']:.2f}</b><br/>
                    &bull; Momentum Decay: <b style="color:{ce_border}; font-size:1.05rem;">{diff_sign}₹{abs(h_ce['decay_diff']):.2f}</b><br/>
                    &bull; Strike Grid: <b style="color:#93c5fd;">{ce_step}-pt Multiples {'(Far Month Liquid)' if ce_far else '(Near Month)'}</b><br/>
                    {ce_shield_html}
                    &bull; 500-pt Hedge ("Helmet"): <b style="color:#60a5fa; font-weight:700;">{h_ce['hedge_strike']} CE</b> (LTP: ₹{h_ce['hedge_ltp']:.2f})<br/>
                    &bull; 1.382 Stop Loss Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_ce['sl_price']:.2f}</b> (+{h_ce['sl_pct']}%)
                </div>
            </div>
            ''', unsafe_allow_html=True)

        with col_pe_box:
            pe_dec = h_pe.get("is_decaying", False)
            pe_border = "#10b981" if pe_dec else "#ef4444"
            pe_badge = "🟢 DECAYING (QUALIFIED TO SELL)" if pe_dec else "🔴 EXPANDING (SKIP)"
            diff_sign_p = "-" if h_pe['decay_diff'] >= 0 else "+"
            pe_far = h_pe.get('is_far_month', False)
            pe_step = h_pe.get('step_size', 100)
            pe_shift = h_pe.get('collision_shifted', False)
            pe_orig = h_pe.get('original_strike', h_pe['sell_strike'])
            pe_shield_html = f"&bull; 🛡️ Anti-Collision: <b style='color:#38bdf8;'>Shifted from {pe_orig} PE (Occupied) ➔ {h_pe['sell_strike']} PE (-{pe_step} pts)</b><br/>" if pe_shift else "&bull; 🛡️ Anti-Collision: <b style='color:#34d399;'>Safe (0 Clash with M-Units/Broker)</b><br/>"

            st.markdown(f'''
            <div style="background: #0f172a; border: 2px solid {pe_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                    <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📉 PUT WING: {h_pe['sell_strike']} PE</span>
                    <span style="font-size:0.80rem; font-weight:800; color:{pe_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {pe_border};">{pe_badge}</span>
                </div>
                <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                    &bull; Today 3 PM LTP: <b style="color:#ffffff; font-size:1.05rem;">₹{h_pe['sell_ltp']:.2f}</b><br/>
                    &bull; Yesterday Reference Price: <b style="color:#cbd5e1;">₹{h_pe['yesterday_anchor']:.2f}</b><br/>
                    &bull; Momentum Decay: <b style="color:{pe_border}; font-size:1.05rem;">{diff_sign_p}₹{abs(h_pe['decay_diff']):.2f}</b><br/>
                    &bull; Strike Grid: <b style="color:#93c5fd;">{pe_step}-pt Multiples {'(Far Month Liquid)' if pe_far else '(Near Month)'}</b><br/>
                    {pe_shield_html}
                    &bull; 500-pt Hedge ("Helmet"): <b style="color:#60a5fa; font-weight:700;">{h_pe['hedge_strike']} PE</b> (LTP: ₹{h_pe['hedge_ltp']:.2f})<br/>
                    &bull; 1.382 Stop Loss Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_pe['sl_price']:.2f}</b> (+{h_pe['sl_pct']}%)
                </div>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown(f'''
        <div style="background: #0f172a; border: 1.5px solid #ff5722; border-left: 6px solid #ff5722; padding: 14px 20px; border-radius: 8px; margin: 16px 0; color: #ffffff; font-size: 0.95rem;">
            <b style="color: #ff8a65;">System Audit Result:</b> <span style="color: #ffffff; font-weight: 600;">{inspection['status_msg']}</span>
        </div>
        ''', unsafe_allow_html=True)

        # STEP 2: EXECUTION BUTTONS (ONLY ENABLED IF LOCKED)
        st.markdown('<p class="section-title" style="margin-top:16px;">🚀 STEP 2: EXECUTE OR ARM POD</p>', unsafe_allow_html=True)

        if not is_locked:
            st.warning("⚠️ Pod settings must be LOCKED above before live execution or 3:00 PM auto-audit can be armed.")
        else:
            pod_unit = st.selectbox("Assign to Pod Identifier", ["OS1", "OS2", "OS3", "OS4", "OS5"], index=0, key="os_tab_pod_select")
            has_traded = db.has_os_traded_today(pod_unit)

            if has_traded:
                st.warning(f"⚠️ Unit {pod_unit} has already executed a trade today ('Din mein sirf ek hi baar trade karna hai').")
                force_ovr = st.checkbox("Force Override Daily Trade Limit", value=False, key="os_tab_force_ovr")
            else:
                force_ovr = False

            act_c1, act_c2 = st.columns(2)
            with act_c1:
                if st.button("🚀 Execute Qualified Decaying Trade(s) Now", key="btn_exec_os_now", use_container_width=True, disabled=(has_traded and not force_ovr)):
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
                            force_override_daily_limit=force_ovr,
                            step_size=selected_step
                        )
                        if res.get("ok"):
                            st.success(res.get("message"))
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res.get("message"))

            with act_c2:
                if st.button("⏱️ Arm for 3:00 PM Auto-Audit Only", key="btn_arm_os_3pm", use_container_width=True):
                    res = deploy_os_unit(
                        unit_name=pod_unit,
                        expiry_date=selected_exp,
                        lots=lots,
                        lot_size=user_lot_size,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        deploy_now=False,
                        step_size=selected_step
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

            act_c1, act_c2, act_c3, act_c4 = st.columns([1.2, 1.2, 1.5, 2.2])
            with act_c1:
                if st.button("💰 Lock Hedge Profit", key=f"btn_lock_h_{b['block_id']}", use_container_width=True):
                    hedges = [s for s in db.get_strikes_by_block(b["block_id"], status_filter="OPEN") if s["leg_type"] == "HEDGE_BUY"]
                    for h in hedges:
                        bm.close_hedge_strike_now(h["strike_id"])
                    st.success("Hedge profits locked!")
                    st.rerun()
            with act_c2:
                if st.button("🛑 Square Off Pod", key=f"btn_sqoff_{b['block_id']}", use_container_width=True):
                    bm.kill_block_now(b["block_id"])
                    st.warning(f"Pod {unit_id} squared off!")
                    st.rerun()
            with act_c3:
                if st.button("🔄 Reset Daily Flag", key=f"btn_reset_d_{b['block_id']}", use_container_width=True, help="Resets today's trade flag allowing another trade in this pod."):
                    db.reset_os_daily_trade_flag(unit_id)
                    st.success(f"Daily trade flag reset for {unit_id}.")
                    st.rerun()
            with act_c4:
                if st.button(f"💥 Wipe Out & Reset {unit_id}", key=f"btn_wipeout_{b['block_id']}", use_container_width=True, type="primary", help="Closes live broker positions, deletes pod from DB, and unlocks settings for next month deployment."):
                    with st.spinner(f"Wiping out {unit_id} on broker and DB..."):
                        w_res = wipeout_os_unit_now(unit_id, sync_live=True)
                    if w_res.get("ok"):
                        st.success(w_res.get("message"))
                    else:
                        st.error(w_res.get("message"))
                    time.sleep(1)
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)
