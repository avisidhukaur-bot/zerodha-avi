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
    unit_name = block.get("anchor_unit_name") or f"M{block_num}"
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

    # Regime calculation with hysteresis buffer
    new_regime = old_regime
    if old_regime == "BULLISH":
        bearish_trigger = anchor - buffer_pts
        if current_spot < bearish_trigger:
            new_regime = "BEARISH"
            _log(f"[UNIT-FLIP] Unit {unit_name} Spot ₹{current_spot:.2f} < Bearish Trigger ₹{bearish_trigger:.2f} (Anchor {anchor:.2f} - Buffer {buffer_pts:.2f}). Flipping BULLISH ➔ BEARISH!", "WARN")
        else:
            new_regime = "BULLISH"
    elif old_regime == "BEARISH":
        bullish_trigger = anchor + buffer_pts
        if current_spot > bullish_trigger:
            new_regime = "BULLISH"
            _log(f"[UNIT-FLIP] Unit {unit_name} Spot ₹{current_spot:.2f} > Bullish Trigger ₹{bullish_trigger:.2f} (Anchor {anchor:.2f} + Buffer {buffer_pts:.2f}). Flipping BEARISH ➔ BULLISH!", "WARN")
        else:
            new_regime = "BEARISH"
    else:
        # Initial resolution
        if current_spot >= anchor:
            new_regime = "BULLISH"
        else:
            new_regime = "BEARISH"
        _log(f"[UNIT-INIT] Unit {unit_name} regime initialized to {new_regime} (Spot ₹{current_spot:.2f} vs Anchor ₹{anchor:.2f})", "REGIME")

    db.update_block_regime(block_id, new_regime)

    regime_shifted = (new_regime != old_regime and old_regime in ("BULLISH", "BEARISH")) or force_eval

    # In V5.0 'Old & Gold' Architecture:
    # 1. Intraday anchor crossings do NOT liquidate open trades (positions breathe for theta decay).
    # 2. At 15:00 IST (3:00 PM), the Continuation Decision officially continues favorable side and closes counter side.
    # 3. Kill & Flip is only executed if force_eval is True or if regime_mode is explicitly set to AUTO_FLIP.
    regime_mode = db.get("regime_mode", "V5_DECOUPLED").upper()
    allow_intraday_liquidate = (regime_mode == "AUTO_FLIP") or force_eval

    closed_opposing_count = 0
    deployed_aligned_count = 0
    closed_strike_summaries = []

    if regime_shifted and allow_intraday_liquidate:
        _log(f"Unit {unit_name} executing Isolated Kill & Flip: {old_regime} ➔ {new_regime} (Spot=₹{current_spot:.2f}, Anchor=₹{anchor:.2f})", "ALERT")
        opposing_opt = "CE" if new_regime == "BULLISH" else "PE"
        aligned_opt = "PE" if new_regime == "BULLISH" else "CE"

        # Phase 1: Emergency cover opposing short legs in this unit ONLY
        open_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN")
        for s in open_strikes:
            if s["leg_type"] == "SELL" and s["option_type"].upper() == opposing_opt:
                strike_id = s["strike_id"]
                _log(f"[UNIT-{unit_name}-KILL] Emergency Market-Cover for opposing strike {s['strike_price']} {s['option_type']}...", "ALERT")
                try:
                    res = bm.close_strike(strike_id, close_hedge=False)
                    if res.get("ok"):
                        closed_opposing_count += 1
                        closed_strike_summaries.append(f"Unit {unit_name} Block #{block_num} | {s['strike_price']} {s['option_type']} SELL")
                except Exception as k_err:
                    _log(f"[UNIT-{unit_name}-KILL-EXCEPTION] Error: {k_err}", "ERROR")

        # Phase 2: Deploy trend-aligned strikes in this unit ONLY
        strikes = db.get_strikes_by_block(block_id)
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
                            _log(f"[UNIT-{unit_name}-DEPLOY] Deploying trend-aligned strike {s['strike_price']} {s['option_type']} (LTP ₹{s_ltp:.2f} <= Anchor ₹{anchor_p:.2f})...", "OK")
                            exec_res = bm.execute_strike(strike_id)
                            if exec_res.get("ok"):
                                deployed_aligned_count += 1
                    except Exception as d_err:
                        _log(f"[UNIT-{unit_name}-DEPLOY-EXCEPTION] Error: {d_err}", "ERROR")

        # Telegram Alert for Unit Regime Shift
        if new_regime != old_regime and old_regime in ("BULLISH", "BEARISH"):
            try:
                alert_text = (
                    f"🧭 <b>UNIT {unit_name} REGIME SHIFT</b> 🧭\n"
                    f"Unit: <b>{unit_name}</b> (Block #{block_num})\n"
                    f"Transition: <b>{old_regime} ➔ {new_regime}</b>\n"
                    f"Live Spot: ₹{current_spot:,.2f} | Unit Anchor: ₹{anchor:,.2f} (±{buffer_pts:.1f}pts)\n"
                    f"Opposing Covered: {closed_opposing_count} leg(s)\n"
                    f"Trend-Aligned Deployed: {deployed_aligned_count} leg(s)\n"
                    f"<i>Unit Pod Isolation: Other units unaffected.</i>"
                )
                tg.send(alert_text)
            except Exception as tg_err:
                _log(f"Error sending unit regime shift alert: {tg_err}", "WARN")
    elif regime_shifted:
        _log(f"Unit {unit_name} Regime shifted {old_regime} ➔ {new_regime} (Spot ₹{current_spot:.2f} vs Anchor ₹{anchor:.2f}). V5 Intraday Decoupled: Positions held peacefully for theta decay.", "INFO")

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


def execute_3pm_master_anchor_decision(current_spot: Optional[float] = None, force_decision: bool = False) -> Dict[str, Any]:
    """
    V5.0 'Old & Gold' Architecture: 3:00 PM Master Anchor Continuation Decision (15:00 IST).
    At 15:00 IST:
    1. Fetches live NIFTY Spot.
    2. For each active unit:
       - Compares Spot vs Unit Master Anchor.
       - If Bullish (Spot >= Anchor):
           * Put Sell marked CONTINUED (held overnight).
           * Call Sell closed on broker + marked CLOSED.
           * Active Call Hedge closed on broker + marked CLOSED.
           * Orphan Hedges preserved untouched.
       - If Bearish (Spot < Anchor):
           * Call Sell marked CONTINUED (held overnight).
           * Put Sell closed on broker + marked CLOSED.
           * Active Put Hedge closed on broker + marked CLOSED.
           * Orphan Hedges preserved untouched.
       - Dispatches Telegram alert with decision and summary.
    """
    import block_manager as bm

    if current_spot is None or current_spot <= 0:
        current_spot = get_current_nifty_spot()

    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    results = []

    for b in active_blocks:
        block_id = b["block_id"]
        block_num = b.get("block_number", block_id)
        unit_name = b.get("anchor_unit_name") or f"M{block_num}"
        anchor = float(b.get("master_anchor_price") or 0.0)

        if anchor <= 0:
            continue

        is_bullish = current_spot >= anchor
        decision_direction = "BULLISH" if is_bullish else "BEARISH"
        continued_opt = "PE" if is_bullish else "CE"
        closed_opt = "CE" if is_bullish else "PE"

        continued_count = 0
        closed_sell_count = 0
        closed_hedge_count = 0
        orphan_preserved_count = 0

        # Get all strikes in this block
        strikes = db.get_strikes_by_block(block_id)
        for s in strikes:
            s_id = s["strike_id"]
            status = s["status"]
            opt_type = s["option_type"].upper()
            leg_type = s["leg_type"].upper()

            # Winning side sell leg -> Mark CONTINUED (Positional overnight carry forward)
            if leg_type == "SELL" and opt_type == continued_opt and status == "OPEN":
                db.update_strike_trade_state(s_id, "CONTINUED")
                h_id = s.get("hedge_strike_id")
                if h_id:
                    db.update_strike_trade_state(h_id, "CONTINUED")
                continued_count += 1
                _log(f"[3PM-DECISION] Unit {unit_name}: {s['strike_price']} {opt_type} SELL & Hedge marked CONTINUED for overnight holding.", "OK")

            # Winning side hedge leg -> Mark CONTINUED
            elif leg_type == "HEDGE_BUY" and opt_type == continued_opt and status == "OPEN":
                db.update_strike_trade_state(s_id, "CONTINUED")

            # Losing side sell leg -> Close gracefully
            elif leg_type == "SELL" and opt_type == closed_opt and status == "OPEN":
                res = bm.close_strike(s_id, close_hedge=False)
                if res.get("ok"):
                    closed_sell_count += 1
                    db.update_strike_trade_state(s_id, "CLOSED")
                    _log(f"[3PM-DECISION] Unit {unit_name}: {s['strike_price']} {opt_type} SELL squared off.", "ALERT")

            # Losing side active hedge -> Close gracefully
            elif leg_type == "HEDGE_BUY" and opt_type == closed_opt and status == "OPEN":
                # Check if it's an orphan or paired
                is_orphan = not db.get_strike(s.get("hedge_strike_id", 0)) or db.get_strike(s.get("hedge_strike_id", 0)).get("status") != "OPEN"
                if is_orphan:
                    # Invariant 5: Preserve orphan hedges untouched!
                    db.update_strike_trade_state(s_id, "ORPHAN")
                    orphan_preserved_count += 1
                    _log(f"[3PM-DECISION] Unit {unit_name}: Orphan Hedge {s['strike_price']} {opt_type} PRESERVED untouched.", "INFO")
                else:
                    res = bm.close_strike(s_id, close_hedge=False)
                    if res.get("ok"):
                        closed_hedge_count += 1
                        db.update_strike_trade_state(s_id, "CLOSED")

        # Dispatched Telegram decision
        try:
            tg.send(
                f"⏰ <b>3:00 PM MASTER ANCHOR CONTINUATION DECISION</b> ⏰\n"
                f"Unit: <b>{unit_name}</b> (Block #{block_num})\n"
                f"Live Spot: ₹<b>{current_spot:,.2f}</b> | Master Anchor: ₹<b>{anchor:,.2f}</b>\n"
                f"Outcome: <b>{decision_direction}</b> ({continued_opt} CONTINUED)\n"
                f"✅ Overnight Continued: <b>{continued_count}</b> leg(s) ({continued_opt})\n"
                f"🛑 Counter Closed: <b>{closed_sell_count}</b> sell(s), <b>{closed_hedge_count}</b> hedge(s)\n"
                f"🛡️ Orphan Hedges Preserved: <b>{orphan_preserved_count}</b>\n"
                f"<i>V5.0 'Old & Gold' Architecture</i>"
            )
        except Exception as e:
            _log(f"Error sending 3PM Telegram alert: {e}", "WARN")

        results.append({
            "block_id": block_id,
            "unit_name": unit_name,
            "anchor": anchor,
            "spot": current_spot,
            "decision": decision_direction,
            "continued_count": continued_count,
            "closed_sell_count": closed_sell_count,
            "closed_hedge_count": closed_hedge_count,
            "orphan_preserved_count": orphan_preserved_count
        })

    return {
        "ok": True,
        "spot": current_spot,
        "results": results,
        "message": f"3:00 PM Continuation decision executed across {len(results)} active unit(s)."
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


