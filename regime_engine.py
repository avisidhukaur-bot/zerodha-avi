"""
regime_engine.py -- Zerodha OptionSelling Engine | Brick 3: Master Regime Evaluator
===================================================================================
Reference: memory.md & Bharat Master Nifty Anchor Blueprint (V2.0)
Version  : 2.0 SINGLE-DIRECTIONAL REGIME GOVERNOR
Date     : June 2026

MASTER REGIME GOVERNOR (Macro Controller above individual strike factory rules):
  - Single-Directional Exposure: At any moment, the engine trades ONLY CALLS or ONLY PUTS.
  - Live Nifty Spot >= Master Anchor -> 🟢 BULLISH REGIME (Only Sell PEs | CE Dormant / Muted)
  - Live Nifty Spot <  Master Anchor -> 🔴 BEARISH REGIME (Only Sell CEs | PE Dormant / Muted)

KILL & FLIP AUTOMATIC TRANSITION PROTOCOL:
  Phase 1: Emergency Square-Off Opposing Side (Zero-Lag Buy-To-Cover Market Order)
  Phase 2: Deploy Trend-Aligned Side (Buy Hedge -> Sell Leg for Pending Strikes)
  Whipsaw Guard: Configurable hysteresis buffer (±10 to ±15 points)
"""

import sys
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import pytz

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg
from kite_executor import kite_executor
import telegram_bot as tg

IST = pytz.timezone("Asia/Kolkata")


def _ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str, level: str = "INFO") -> None:
    print(f"[REGIME_ENGINE][{level}] {msg}")


def get_current_nifty_spot() -> float:
    """Fetches current live NIFTY 50 spot price via kite_executor adapter."""
    return kite_executor.get_nifty_spot()



def is_strike_allowed_by_regime(option_type: str, block: Optional[dict] = None) -> Tuple[bool, str]:
    """
    Checks if a given option_type ('CE' or 'PE') is permitted under Master Regime.
    In V3.0, prioritizes the block's own Unit Master Anchor and regime state.
    Returns: (is_allowed: bool, reason: str)
    """
    # OS units (Option Selling) are pure option decay driven — strictly bypass spot regime!
    if block:
        uname = (block.get("anchor_unit_name") or "").strip().upper()
        if uname.startswith("OS"):
            return True, f"OS Unit {uname} is pure option decay driven (Spot regime bypassed)"

    mode = db.get_regime_mode()
    if mode == "OFF":
        return True, "Regime governor is OFF (Dual-sided allowed)"

    opt_type_upper = str(option_type).strip().upper()

    # 1. Block-Level Unit Regime (V3.0 Autonomous Pods)
    if block:
        if not block.get("auto_regime_enabled", 1):
            return True, f"Unit {block.get('anchor_unit_name', 'M')} auto-governor is disabled"

        b_anchor = float(block.get("master_anchor_price") or 0.0)
        if b_anchor > 0:
            b_regime = (block.get("current_regime") or "NEUTRAL").strip().upper()
            unit_name = block.get("anchor_unit_name") or f"M{block.get('block_number', '')}"
            if b_regime == "BULLISH":
                if opt_type_upper == "PE":
                    return True, f"🟢 BULLISH Unit {unit_name}: PE Selling Active"
                else:
                    return False, f"🔴 MUTED: Unit {unit_name} is BULLISH (Only PE selling allowed, CE muted)"
            elif b_regime == "BEARISH":
                if opt_type_upper == "CE":
                    return True, f"🔴 BEARISH Unit {unit_name}: CE Selling Active"
                else:
                    return False, f"🟢 MUTED: Unit {unit_name} is BEARISH (Only CE selling allowed, PE muted)"
            else:
                return True, f"⚪ NEUTRAL Unit {unit_name}: Dual-sided allowed"

    # 2. Global Master Anchor Fallback (V2.0 Legacy)
    anchor = db.get_master_nifty_anchor()
    if anchor <= 0:
        return True, "Master Anchor not set (Dual-sided allowed)"

    active_regime = db.get_active_regime()

    if active_regime == "BULLISH":
        if opt_type_upper == "PE":
            return True, "🟢 BULLISH Regime: PE Selling Active"
        else:
            return False, "🔴 MUTED: Regime is BULLISH (Only PE selling allowed, CE muted)"

    elif active_regime == "BEARISH":
        if opt_type_upper == "CE":
            return True, "🔴 BEARISH Regime: CE Selling Active"
        else:
            return False, "🟢 MUTED: Regime is BEARISH (Only CE selling allowed, PE muted)"

    # NEUTRAL
    return True, "NEUTRAL Regime (Both sides allowed)"


def evaluate_block_regime(block: dict, current_spot: Optional[float] = None, force_eval: bool = False) -> Dict[str, Any]:
    """
    Evaluates the directional regime for a single block/unit (V3.0 Multi-Anchor Pod).
    Enforces isolated Kill & Flip strictly for this block without affecting other units.
    """
    import block_manager as bm

    block_id = block["block_id"]
    block_num = block.get("block_number", block_id)
    unit_name = (block.get("anchor_unit_name") or f"M{block_num}").strip().upper()

    # STRICT FIREWALL: OS units (Option Selling) are driven by pure option decay at 3:00 PM.
    # They have ZERO relation to spot price and MUST NEVER be evaluated or auto-traded by the Spot Regime Engine!
    if unit_name.startswith("OS"):
        return {
            "block_id": block_id,
            "unit_name": unit_name,
            "anchor": 0.0,
            "buffer": 0.0,
            "spot": current_spot if current_spot else 0.0,
            "regime": "NEUTRAL",
            "shifted": False,
            "closed_opposing": 0,
            "deployed_aligned": 0,
            "message": f"Unit {unit_name} is an OS Option Selling pod. Spot regime evaluation strictly ignored."
        }

    anchor = float(block.get("master_anchor_price") or 0.0)
    buffer_pts = float(block.get("regime_buffer") or 15.0)
    old_regime = (block.get("current_regime") or "NEUTRAL").strip().upper()

    if current_spot is None or current_spot <= 0:
        current_spot = get_current_nifty_spot()

    if anchor <= 0:
        # Fallback to global master anchor if block anchor is unset
        global_anchor = db.get_master_nifty_anchor()
        if global_anchor > 0:
            anchor = global_anchor
        else:
            if old_regime != "NEUTRAL":
                db.update_block_regime(block_id, "NEUTRAL")
            return {
                "block_id": block_id,
                "unit_name": unit_name,
                "anchor": 0.0,
                "buffer": buffer_pts,
                "spot": current_spot,
                "regime": "NEUTRAL",
                "shifted": False,
                "closed_opposing": 0,
                "deployed_aligned": 0,
                "message": f"Unit {unit_name} Anchor not set."
            }

    # ── Regime calculation with hysteresis buffer & 5-minute stay confirmation timer ──
    # Minimum continuous stay duration in seconds (default: 300s = 5 minutes)
    required_stay_sec = float(db.get("regime_stay_duration_sec", "300") or 300)
    now_ts = time.time()

    new_regime = old_regime
    if old_regime == "BULLISH":
        bearish_trigger = anchor - buffer_pts
        if current_spot < bearish_trigger:
            if force_eval:
                new_regime = "BEARISH"
                db.set(f"breakout_ts_bearish_{block_id}", "0")
                _log(f"[UNIT-FLIP] Unit {unit_name} Spot ₹{current_spot:.2f} < Bearish Trigger ₹{bearish_trigger:.2f} (Force Eval). Flipping BULLISH ➔ BEARISH!", "WARN")
            else:
                raw_ts = db.get(f"breakout_ts_bearish_{block_id}", "0")
                b_start = float(raw_ts) if raw_ts and raw_ts != "0" else 0.0
                if b_start <= 0:
                    db.set(f"breakout_ts_bearish_{block_id}", str(now_ts))
                    new_regime = "BULLISH"
                    _log(f"[UNIT-STAY-TIMER] Unit {unit_name} Spot ₹{current_spot:.2f} < Bearish Trigger ₹{bearish_trigger:.2f}. Timer started: awaiting {required_stay_sec:.0f}s (5 min) sustained breakdown.", "INFO")
                else:
                    elapsed = now_ts - b_start
                    if elapsed >= required_stay_sec:
                        new_regime = "BEARISH"
                        db.set(f"breakout_ts_bearish_{block_id}", "0")
                        _log(f"[UNIT-FLIP-CONFIRMED] Unit {unit_name} Spot ₹{current_spot:.2f} stayed below ₹{bearish_trigger:.2f} for {elapsed:.1f}s (>= {required_stay_sec:.0f}s). Confirmed 5-Min Breakdown! Flipping BULLISH ➔ BEARISH!", "WARN")
                    else:
                        new_regime = "BULLISH"
                        _log(f"[UNIT-AWAITING-CONFIRMATION] Unit {unit_name} Spot ₹{current_spot:.2f} < Bearish Trigger ₹{bearish_trigger:.2f} ({elapsed:.0f}/{required_stay_sec:.0f}s sustained). Maintaining BULLISH until 5-min confirmed.", "INFO")
        else:
            # Spot recovered back above bearish trigger -> reset timer!
            raw_ts = db.get(f"breakout_ts_bearish_{block_id}", "0")
            if raw_ts and raw_ts != "0":
                db.set(f"breakout_ts_bearish_{block_id}", "0")
                _log(f"[UNIT-STAY-RESET] Unit {unit_name} Spot ₹{current_spot:.2f} bounced back above Bearish Trigger ₹{bearish_trigger:.2f}. Resetting 5-min timer.", "INFO")
            new_regime = "BULLISH"

    elif old_regime == "BEARISH":
        bullish_trigger = anchor + buffer_pts
        if current_spot > bullish_trigger:
            if force_eval:
                new_regime = "BULLISH"
                db.set(f"breakout_ts_bullish_{block_id}", "0")
                _log(f"[UNIT-FLIP] Unit {unit_name} Spot ₹{current_spot:.2f} > Bullish Trigger ₹{bullish_trigger:.2f} (Force Eval). Flipping BEARISH ➔ BULLISH!", "WARN")
            else:
                raw_ts = db.get(f"breakout_ts_bullish_{block_id}", "0")
                b_start = float(raw_ts) if raw_ts and raw_ts != "0" else 0.0
                if b_start <= 0:
                    db.set(f"breakout_ts_bullish_{block_id}", str(now_ts))
                    new_regime = "BEARISH"
                    _log(f"[UNIT-STAY-TIMER] Unit {unit_name} Spot ₹{current_spot:.2f} > Bullish Trigger ₹{bullish_trigger:.2f}. Timer started: awaiting {required_stay_sec:.0f}s (5 min) sustained breakout.", "INFO")
                else:
                    elapsed = now_ts - b_start
                    if elapsed >= required_stay_sec:
                        new_regime = "BULLISH"
                        db.set(f"breakout_ts_bullish_{block_id}", "0")
                        _log(f"[UNIT-FLIP-CONFIRMED] Unit {unit_name} Spot ₹{current_spot:.2f} stayed above ₹{bullish_trigger:.2f} for {elapsed:.1f}s (>= {required_stay_sec:.0f}s). Confirmed 5-Min Breakout! Flipping BEARISH ➔ BULLISH!", "WARN")
                    else:
                        new_regime = "BEARISH"
                        _log(f"[UNIT-AWAITING-CONFIRMATION] Unit {unit_name} Spot ₹{current_spot:.2f} > Bullish Trigger ₹{bullish_trigger:.2f} ({elapsed:.0f}/{required_stay_sec:.0f}s sustained). Maintaining BEARISH until 5-min confirmed.", "INFO")
        else:
            # Spot fell back below bullish trigger -> reset timer!
            raw_ts = db.get(f"breakout_ts_bullish_{block_id}", "0")
            if raw_ts and raw_ts != "0":
                db.set(f"breakout_ts_bullish_{block_id}", "0")
                _log(f"[UNIT-STAY-RESET] Unit {unit_name} Spot ₹{current_spot:.2f} fell back below Bullish Trigger ₹{bullish_trigger:.2f}. Resetting 5-min timer.", "INFO")
            new_regime = "BEARISH"
    else:
        # Initial resolution with Hysteresis Buffer Guard
        bullish_trigger = anchor + buffer_pts
        bearish_trigger = anchor - buffer_pts
        if current_spot >= bullish_trigger:
            new_regime = "BULLISH"
        elif current_spot <= bearish_trigger:
            new_regime = "BEARISH"
        else:
            new_regime = "NEUTRAL"
        _log(f"[UNIT-INIT] Unit {unit_name} regime initialized to {new_regime} (Spot ₹{current_spot:.2f} vs Anchor ₹{anchor:.2f} ± {buffer_pts:.1f}pts)", "REGIME")

    db.update_block_regime(block_id, new_regime)

    regime_shifted = (new_regime != old_regime and old_regime in ("BULLISH", "BEARISH", "NEUTRAL") and new_regime in ("BULLISH", "BEARISH")) or force_eval

    closed_opposing_count = 0
    deployed_aligned_count = 0
    closed_strike_summaries = []

    opposing_opt = "CE" if new_regime == "BULLISH" else "PE"
    aligned_opt = "PE" if new_regime == "BULLISH" else "CE"

    strikes = db.get_strikes_by_block(block_id)
    has_open_aligned = any(
        s["leg_type"] == "SELL" and s["status"] == "OPEN" and s["option_type"].upper() == aligned_opt
        for s in strikes
    )
    has_open_opposing = any(
        s["leg_type"] == "SELL" and s["status"] == "OPEN" and s["option_type"].upper() == opposing_opt
        for s in strikes
    )

    now_ist_str = datetime.now(IST).strftime("%H:%M")
    is_3pm_or_later = (now_ist_str >= "15:00") or force_eval

    # Phase 1: Enforce single-direction for THIS UNIT at 3:00 PM: Auto-close open opposing SELL legs
    # V5.0 DECOUPLED MASTER ANCHOR RULE: Intraday market crosses of the Master Anchor
    # do NOT close trades continuously during market hours. Closures are evaluated strictly at 3:00 PM (15:00 IST).
    if is_3pm_or_later and (regime_shifted or has_open_opposing):
        open_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN")
        for s in open_strikes:
            if s["leg_type"] == "SELL" and s["option_type"].upper() == opposing_opt:
                strike_id = s["strike_id"]
                _log(f"[UNIT-{unit_name}-KILL] Market-Cover for opposing strike {s['strike_price']} {s['option_type']} (3:00 PM Continuation)...", "ALERT")
                try:
                    res = bm.close_strike(strike_id, close_hedge=False)
                    if res.get("ok"):
                        closed_opposing_count += 1
                        closed_strike_summaries.append(f"Unit {unit_name} Block #{block_num} | {s['strike_price']} {s['option_type']} SELL")
                except Exception as k_err:
                    _log(f"[UNIT-{unit_name}-KILL-EXCEPTION] Error: {k_err}", "ERROR")
    elif regime_shifted and not is_3pm_or_later:
        _log(f"[UNIT-{unit_name}] Intraday Spot cross detected ({new_regime}). In V5.0, active trades are held peacefully for theta decay; Master Anchor continuation is evaluated at 3:00 PM IST.", "INFO")

    # Phase 2: Asymmetric Trend-Aligned Deployment for THIS UNIT (Before 14:55 Cutoff)
    # V6.0 / V8.0 ASYMMETRIC EXECUTION RULE:
    # When Spot crosses Master Anchor / Magical Line, initiate trend-aligned side (e.g. Call sell in Bearish regime).
    # An existing opposing leg is NOT cut midday and does NOT block initiation; it is protected by its 25% SL.
    today_ymd = datetime.now(IST).strftime("%Y-%m-%d")
    is_3pm_frozen = (now_ist_str >= "14:55") or (db.get("last_3pm_decision_date", "") == today_ymd)
    
    # Gurjeet Mamu's Law (23-Nov-2026): M2 and M3 are 100% full M-Units!
    # Super Sukhoi only spawns the unit and sets its Anchor. Once spawned,
    # M2 and M3 run the exact same Asymmetric Dual-Wing Engine (Call + Put with 3 PM square-off).
    should_deploy_aligned = (
        new_regime in ("BULLISH", "BEARISH")
        and not has_open_aligned
        and not is_3pm_frozen
        and not unit_name.startswith("OS")
    )

    if should_deploy_aligned:
        if has_open_opposing:
            _log(f"[UNIT-{unit_name}] Asymmetric Directional Initiation: {aligned_opt} triggered under {new_regime} Regime (Spot ₹{current_spot:,.2f} vs Anchor ₹{anchor:,.2f}). Running {opposing_opt} protected by 25% SL until 3:00 PM audit.", "INFO")

        jit_deployed = False
        if unit_name.startswith("M") and hasattr(bm, "hunt_and_execute_jit_m_strike"):
            # V6.3 JIT Dynamic Auto-Hunter:
            # Dynamically find current EVEN 100-multiple closest to target premium (~200) and enforce floor
            try:
                jit_res = bm.hunt_and_execute_jit_m_strike(block_id, aligned_opt)
                if jit_res.get("ok"):
                    deployed_aligned_count += 1
                    jit_deployed = True
                    _log(f"✅ [ASYMMETRIC_DEPLOY] Trend-aligned {aligned_opt} spread executed via JIT Hunter under {new_regime} regime.", "OK")
            except Exception as j_err:
                _log(f"[JIT-M-HUNTER-ERROR] {j_err}. Falling back to pre-drafted strike...", "WARN")

        if not jit_deployed:
            # Fallback to pre-drafted PENDING strike in block
            for s in strikes:
                if s["leg_type"] == "SELL" and s["option_type"].upper() == aligned_opt:
                    strike_id = s["strike_id"]
                    status = s.get("status")
                    if status in ("PENDING", "CLOSED"):
                        anchor_p = float(s.get("anchor_price", 0.0))
                        try:
                            import pnl_engine as pe
                            s_ltp = pe.fetch_ltp(s, force_refresh=True)
                            buffer_tol = float(db.get("buffer_tolerance", "2.0"))
                            if (0 < s_ltp <= anchor_p + buffer_tol) or anchor_p <= 0 or (status == "PENDING" and s_ltp <= 0):
                                _log(f"[UNIT-{unit_name}-DEPLOY] Deploying trend-aligned pre-drafted strike {s['strike_price']} {s['option_type']} (LTP ₹{s_ltp:.2f} <= Anchor ₹{anchor_p:.2f})...", "OK")
                                exec_res = bm.execute_strike(strike_id)
                                if exec_res.get("ok"):
                                    deployed_aligned_count += 1
                        except Exception as d_err:
                            _log(f"[UNIT-{unit_name}-DEPLOY-EXCEPTION] Error: {d_err}", "ERROR")

    # Telegram Alert for Unit Regime Shift or Asymmetric Deployment
    if (new_regime != old_regime and old_regime in ("BULLISH", "BEARISH")) or deployed_aligned_count > 0:
        try:
            alert_text = (
                f"🧭 <b>UNIT {unit_name} REGIME UPDATE</b> 🧭\n"
                f"Unit: <b>{unit_name}</b> (Block #{block_num})\n"
                f"Regime: <b>{new_regime}</b> (Anchor: ₹{anchor:,.2f})\n"
                f"Live Spot: ₹{current_spot:,.2f} | Distance: {current_spot - anchor:+.2f} pts\n"
                f"Opposing Covered: {closed_opposing_count} leg(s)\n"
                f"Trend-Aligned Deployed: {deployed_aligned_count} leg(s)\n"
                f"<i>Unit Pod Isolation: Other units unaffected.</i>"
            )
            tg.send(alert_text)
        except Exception as tg_err:
            _log(f"Error sending unit regime shift alert: {tg_err}", "WARN")

    return {
        "block_id": block_id,
        "unit_name": unit_name,
        "anchor": anchor,
        "buffer": buffer_pts,
        "spot": current_spot,
        "regime": new_regime,
        "shifted": regime_shifted,
        "closed_opposing": closed_opposing_count,
        "deployed_aligned": deployed_aligned_count,
    }


def evaluate_all_block_regimes(current_spot: Optional[float] = None, force_eval: bool = False) -> Dict[str, Any]:
    """
    Evaluates Master Regime for all active blocks independently (V3.0 Multi-Anchor Grid).
    Also updates legacy global anchor evaluation.
    """
    if current_spot is None or current_spot <= 0:
        current_spot = get_current_nifty_spot()

    # 1. Update Global Legacy Regime
    global_res = evaluate_master_regime(current_spot=current_spot, force_eval=force_eval)

    # 2. Evaluate each Active Unit independently
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    unit_results = []
    for b in active_blocks:
        if not b.get("is_enabled", 1):
            continue
        uname = (b.get("anchor_unit_name") or "").strip().upper()
        if uname.startswith("OS"):
            continue  # OS blocks are strictly manual / 3:00 PM option decay driven; NEVER evaluate under spot regime!
        try:
            res = evaluate_block_regime(b, current_spot=current_spot, force_eval=force_eval)
            unit_results.append(res)
        except Exception as e:
            _log(f"Error evaluating regime for Block #{b.get('block_number')}: {e}", "ERROR")

    return {
        "spot": current_spot,
        "global_regime": global_res.get("regime"),
        "unit_results": unit_results
    }


def evaluate_master_regime(current_spot: Optional[float] = None, force_eval: bool = False) -> Dict[str, Any]:
    """
    Legacy Global Master Regime Evaluator.
    """
    import block_manager as bm

    mode = db.get_regime_mode()
    anchor = db.get_master_nifty_anchor()
    buffer_pts = db.get_regime_buffer()
    old_regime = db.get_active_regime()

    if current_spot is None or current_spot <= 0:
        current_spot = get_current_nifty_spot()

    # Save last checked spot
    if current_spot > 0:
        db.set("last_master_spot_price", f"{current_spot:.2f}")

    # If Anchor is not set (<= 0), maintain NEUTRAL
    if anchor <= 0:
        if old_regime != "NEUTRAL":
            db.set_active_regime("NEUTRAL")
            _log(f"Master Regime set to NEUTRAL (Anchor={anchor:.2f})", "REGIME")
        return {
            "mode": "AUTO",
            "anchor": anchor,
            "buffer": buffer_pts,
            "spot": current_spot,
            "regime": "NEUTRAL",
            "shifted": False,
            "closed_opposing": 0,
            "deployed_aligned": 0,
            "message": "Master Anchor not set."
        }

    # 100% AUTOMATED REGIME EVALUATION WITH HYSTERESIS BUFFER
    new_regime = old_regime
    if old_regime == "BULLISH":
        bearish_trigger = anchor - buffer_pts
        if current_spot < bearish_trigger:
            new_regime = "BEARISH"
            _log(f"[REGIME-FLIP] Global Spot ₹{current_spot:.2f} < Bearish Trigger ₹{bearish_trigger:.2f}. Flipping BULLISH ➔ BEARISH!", "WARN")
        else:
            new_regime = "BULLISH"
    elif old_regime == "BEARISH":
        bullish_trigger = anchor + buffer_pts
        if current_spot > bullish_trigger:
            new_regime = "BULLISH"
            _log(f"[REGIME-FLIP] Global Spot ₹{current_spot:.2f} > Bullish Trigger ₹{bullish_trigger:.2f}. Flipping BEARISH ➔ BULLISH!", "WARN")
        else:
            new_regime = "BEARISH"
    else:
        if current_spot >= anchor:
            new_regime = "BULLISH"
        else:
            new_regime = "BEARISH"

    db.set_active_regime(new_regime)

    regime_shifted = (new_regime != old_regime and old_regime in ("BULLISH", "BEARISH")) or force_eval

    closed_opposing_count = 0
    deployed_aligned_count = 0

    if regime_shifted:
        opposing_opt = "CE" if new_regime == "BULLISH" else "PE"
        aligned_opt = "PE" if new_regime == "BULLISH" else "CE"

        now_ist_str = datetime.now(IST).strftime("%H:%M")
        is_3pm_or_later = (now_ist_str >= "15:00") or force_eval
        if is_3pm_or_later:
            active_blocks = db.get_all_blocks(status_filter="ACTIVE")
            for b in active_blocks:
                if not b.get("is_enabled", 1):
                    continue
                open_strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
                for s in open_strikes:
                    if s["leg_type"] == "SELL" and s["option_type"].upper() == opposing_opt:
                        strike_id = s["strike_id"]
                        try:
                            res = bm.close_strike(strike_id, close_hedge=False)
                            if res.get("ok"):
                                closed_opposing_count += 1
                        except Exception:
                            pass

                # Phase 2: Deploy trend-aligned side at 3:00 PM decision window
                strikes = db.get_strikes_by_block(b["block_id"])
                for s in strikes:
                    if s["leg_type"] == "SELL" and s["option_type"].upper() == aligned_opt:
                        strike_id = s["strike_id"]
                        status = s.get("status")
                        if status in ("PENDING", "CLOSED"):
                            anchor_p = float(s.get("anchor_price", 0.0))
                            try:
                                import pnl_engine as pe
                                s_ltp = pe.fetch_ltp(s, force_refresh=True)
                                buffer_tol = float(db.get("buffer_tolerance", "2.0"))
                                if (0 < s_ltp <= anchor_p + buffer_tol) or anchor_p <= 0 or (status == "PENDING" and s_ltp <= 0):
                                    exec_res = bm.execute_strike(strike_id)
                                    if exec_res.get("ok"):
                                        deployed_aligned_count += 1
                            except Exception:
                                pass
        else:
            _log(f"[GLOBAL-REGIME] Intraday Spot cross detected ({new_regime}). In V5.0, active trades are held peacefully for theta decay; Master Anchor continuation is evaluated at 3:00 PM IST.", "INFO")

    return {
        "mode": mode,
        "anchor": anchor,
        "buffer": buffer_pts,
        "spot": current_spot,
        "regime": new_regime,
        "shifted": regime_shifted,
        "closed_opposing": closed_opposing_count,
        "deployed_aligned": deployed_aligned_count,
        "message": f"Global regime is {new_regime} (Spot ₹{current_spot:.2f} vs Anchor ₹{anchor:.2f} ± {buffer_pts:.1f}pts)."
    }


def lock_current_spot_as_anchor() -> float:
    """
    1-Click Spot Lock action for Global Master Anchor.
    """
    spot = get_current_nifty_spot()
    if spot > 0:
        db.set_master_nifty_anchor(spot)
        _log(f"1-Click Lock: Master Nifty Anchor locked to live spot ₹{spot:.2f}", "OK")
        evaluate_master_regime(current_spot=spot, force_eval=True)
        try:
            tg.alert_regime_anchor_updated(
                anchor=spot,
                buffer=db.get_regime_buffer(),
                spot=spot,
                mode=db.get_regime_mode()
            )
        except Exception:
            pass
    return spot


def lock_spot_for_unit(block_id: int) -> float:
    """
    1-Click Spot Lock action for a specific Unit (V3.0 Multi-Anchor Pod).
    """
    spot = get_current_nifty_spot()
    if spot > 0:
        block = db.get_block(block_id)
        if block:
            buffer_pts = float(block.get("regime_buffer") or 15.0)
            unit_name = block.get("anchor_unit_name") or f"M{block.get('block_number', block_id)}"
            db.update_block_anchor(block_id, spot, buffer_pts)
            _log(f"1-Click Lock: Unit {unit_name} Anchor locked to live spot ₹{spot:,.2f}", "OK")
            # Refresh block dict and evaluate immediately
            updated_block = db.get_block(block_id)
            evaluate_block_regime(updated_block, current_spot=spot, force_eval=True)
            try:
                tg.send(f"🎯 <b>UNIT {unit_name} ANCHOR LOCKED</b>\nLocked to live spot ₹{spot:,.2f} (Buffer: ±{buffer_pts:.1f}pts).")
            except Exception:
                pass
    return spot


