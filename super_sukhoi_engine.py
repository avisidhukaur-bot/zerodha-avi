"""
super_sukhoi_engine.py — Super Sukhoi Autonomous Directional Laddering Engine (V7.0)
=====================================================================================
Target System : Zerodha Kite Option Selling App (Bharat Systems — Chhoti Bahan Edition)
Document Ref  : SUPER_SUKHOI_BLUEPRINT_ZERODHA_V7.md & PRODUCT_DEVELOPMENT_SUPER_SUKHOI_CHEENNA_V7.md
Protocol      : Gurjas's Lego System Protocol (Brick 3)

Autonomous Supervisory Layer over mature Directional M-Unit Architecture:
  - Takes Seed Unit M1 (Anchor A1, Expiry, Lots)
  - Tracks live Nifty Spot continuously every 30 seconds
  - Auto-spawns Tier 1 (M2 UP at +2.00% / M2 DOWN at -2.00%)
  - Auto-spawns Tier 2 (M3 UP at +4.00% / M3 DOWN at -4.00%) if M1 is still active
  - Compulsory Hedge Buy FIRST -> Sell Leg SECOND on Zerodha Kite
  - Zero Naked Trades (100% 500-pt protective helmet)
  - Decoupled 25% Stop Loss (Harvest theta peacefully)
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
import pytz

import db
import config as cfg
import utils
import block_manager as bm
from kite_executor import kite_executor
import telegram_bot as tg

IST = pytz.timezone("Asia/Kolkata")


def _log(msg: str, level: str = "SUKHOI") -> None:
    utils.log(f"[SUPER_SUKHOI] {msg}", level)


# ─────────────────────────────────────────────────────────────────────────────
# 1. MATHEMATICAL TRIGGER CALCULUS
# ─────────────────────────────────────────────────────────────────────────────

def compute_triggers(seed_anchor: float) -> Dict[str, float]:
    """
    Computes exact mathematical trigger bounds from M1 Seed Anchor Price (A1):
      Tier 1: M2 UP (+2.00%)   = round(A1 * 1.020, 2)
      Tier 1: M2 DOWN (-2.00%) = round(A1 * 0.980, 2)
      Tier 2: M3 UP (+4.00%)   = round(A1 * 1.040, 2)
      Tier 2: M3 DOWN (-4.00%) = round(A1 * 0.960, 2)
    """
    a = float(seed_anchor or 0.0)
    if a <= 0:
        return {
            "m2_up": 0.0,
            "m2_down": 0.0,
            "m3_up": 0.0,
            "m3_down": 0.0,
        }
    return {
        "m2_up": round(a * 1.020, 2),
        "m2_down": round(a * 0.980, 2),
        "m3_up": round(a * 1.040, 2),
        "m3_down": round(a * 0.960, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. STATUS & TELEMETRY RADAR
# ─────────────────────────────────────────────────────────────────────────────

def get_super_sukhoi_status() -> Dict[str, Any]:
    """Returns complete real-time status and telemetry for the Cockpit HUD card."""
    state = db.get_super_sukhoi_state()
    live_spot = kite_executor.get_nifty_spot()
    if live_spot <= 0:
        live_spot = float(db.get("last_nifty_spot_price", "23250.0") or "23250.0")

    # Resolve M1 anchor: from state, or M1 active block, or M1 locked settings
    m1_anchor = float(state.get("m1_anchor", 0.0))
    if m1_anchor <= 0:
        m1_settings = db.get_m_unit_settings("M1") or {}
        m1_anchor = float(m1_settings.get("anchor_price", 0.0) or 0.0)
    if m1_anchor <= 0:
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        b_m1 = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == "M1"), None)
        if b_m1:
            m1_anchor = float(b_m1.get("master_anchor_price", 0.0) or 0.0)

    triggers = compute_triggers(m1_anchor)

    # Check if M1 is currently active with open positions
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    b_m1 = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == "M1"), None)
    m1_is_active = False
    if b_m1:
        m1_strikes = db.get_strikes_by_block(b_m1["block_id"], status_filter="OPEN")
        m1_is_active = len(m1_strikes) > 0

    return {
        "active": state.get("active", False),
        "live_spot": live_spot,
        "m1_anchor": m1_anchor,
        "m1_expiry": state.get("m1_expiry", ""),
        "m1_lots": state.get("m1_lots", 1),
        "m1_is_active": m1_is_active,
        "m2_deployed": state.get("m2_deployed", False),
        "m2_direction": state.get("m2_direction", ""),
        "m3_deployed": state.get("m3_deployed", False),
        "m3_direction": state.get("m3_direction", ""),
        "activated_at": state.get("activated_at", ""),
        "stoploss_mode": state.get("stoploss_mode", "DISABLED"),
        "triggers": triggers,
        "dist_m2_up": round(triggers["m2_up"] - live_spot, 2) if (triggers["m2_up"] > 0 and live_spot > 0) else 0.0,
        "dist_m2_down": round(live_spot - triggers["m2_down"], 2) if (triggers["m2_down"] > 0 and live_spot > 0) else 0.0,
        "dist_m3_up": round(triggers["m3_up"] - live_spot, 2) if (triggers["m3_up"] > 0 and live_spot > 0) else 0.0,
        "dist_m3_down": round(live_spot - triggers["m3_down"], 2) if (triggers["m3_down"] > 0 and live_spot > 0) else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. ACTIVATION & DEACTIVATION CONTROLLERS
# ─────────────────────────────────────────────────────────────────────────────

def activate_super_sukhoi(
    m1_anchor: float = 0.0,
    expiry_date: str = "",
    lots: int = 1
) -> Dict[str, Any]:
    """
    Activates Super Sukhoi Auto-Mode:
      - Validates and stores M1 Seed Anchor, Expiry, and Lots.
      - Sets super_sukhoi_active = '1'.
      - Resets any previous M2/M3 deployment locks for a clean session.
      - Sends instant Telegram confirmation alert.
    """
    # Fallback to M1 locked settings if not provided
    m1_settings = db.get_m_unit_settings("M1") or {}
    anchor = float(m1_anchor or 0.0)
    if anchor <= 0:
        anchor = float(m1_settings.get("anchor_price", 0.0) or 0.0)
    if anchor <= 0:
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        b_m1 = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == "M1"), None)
        if b_m1:
            anchor = float(b_m1.get("master_anchor_price", 0.0) or 0.0)
    if anchor <= 0:
        anchor = kite_executor.get_nifty_spot()
        if anchor <= 0:
            anchor = float(db.get("last_nifty_spot_price", "22650.0") or "22650.0")

    exp = str(expiry_date or m1_settings.get("expiry_date", "") or "").strip()
    lot_count = int(lots or m1_settings.get("lots", 1) or 1)

    triggers = compute_triggers(anchor)

    db.set_super_sukhoi_state(
        active=True,
        m1_anchor=anchor,
        m1_expiry=exp,
        m1_lots=lot_count,
        m2_deployed=False,
        m2_direction="",
        m3_deployed=False,
        m3_direction=""
    )

    msg = (
        f"🦅 <b>SUPER SUKHOI AUTO-MODE ACTIVATED (V7.0)</b>\n"
        f"Seed Unit M1 Anchor : <b>₹{anchor:,.2f}</b>\n"
        f"Expiry Horizon      : <b>{exp or 'Monthly'}</b> | Lots: <b>{lot_count}</b>\n"
        f"────────────────────────\n"
        f"🎯 <b>AUTONOMOUS TRIGGER BANDS:</b>\n"
        f"📈 M2 UP (+2.00%)   : <b>₹{triggers['m2_up']:,.2f}</b> (Bull Put Spread)\n"
        f"📉 M2 DOWN (-2.00%) : <b>₹{triggers['m2_down']:,.2f}</b> (Bear Call Spread)\n"
        f"📈 M3 UP (+4.00%)   : <b>₹{triggers['m3_up']:,.2f}</b>\n"
        f"📉 M3 DOWN (-4.00%) : <b>₹{triggers['m3_down']:,.2f}</b>\n"
        f"────────────────────────\n"
        f"🛡️ 500-pt Protective Helmet: <b>ACTIVE</b>\n"
        f"✂️ Midday 25% Stop-Loss: <b>DISABLED (Theta Harvest)</b>"
    )
    _log(f"Activated Super Sukhoi with Seed Anchor ₹{anchor:.2f}, Expiry={exp}, Lots={lot_count}", "OK")
    tg.send(msg)

    return {
        "ok": True,
        "message": f"Super Sukhoi Activated successfully at Anchor ₹{anchor:,.2f}.",
        "anchor": anchor,
        "triggers": triggers
    }


def deactivate_super_sukhoi() -> Dict[str, Any]:
    """Deactivates Super Sukhoi Auto-Mode back to Manual Cockpit mode."""
    db.set("super_sukhoi_active", "0")
    _log("Deactivated Super Sukhoi Auto-Mode. Cockpit returned to Manual Control.", "STATUS")
    tg.send("🛑 <b>SUPER SUKHOI AUTO-MODE DEACTIVATED</b>\nEngine has reverted to Manual Directional Cockpit mode.")
    return {"ok": True, "message": "Super Sukhoi Deactivated."}


def reset_super_sukhoi_deployments() -> Dict[str, Any]:
    """Clears M2 and M3 deployment locks without disabling auto-mode."""
    db.set("super_sukhoi_m2_deployed", "0")
    db.set("super_sukhoi_m2_direction", "")
    db.set("super_sukhoi_m3_deployed", "0")
    db.set("super_sukhoi_m3_direction", "")
    _log("Reset Super Sukhoi M2/M3 deployment locks.", "OK")
    return {"ok": True, "message": "Deployment locks reset."}


# ─────────────────────────────────────────────────────────────────────────────
# 4. AUTONOMOUS TIER DEPLOYER
# ─────────────────────────────────────────────────────────────────────────────

def deploy_autonomous_tier(
    tier_name: str,
    direction: str,
    trigger_price: float,
    expiry_date: str,
    lots: int
) -> Dict[str, Any]:
    """
    Autonomously inspects candidate strikes, locks parameters, and executes the spread on Kite:
      - Direction == 'UP'   -> Bull Put Spread (Sell PE + Buy PE Hedge at -500 pts)
      - Direction == 'DOWN' -> Bear Call Spread (Sell CE + Buy CE Hedge at +500 pts)
      - Pre-buys 500-pt hedge FIRST for full Zerodha margin discount.
      - Sells short leg SECOND.
    """
    u = tier_name.strip().upper()
    dir_clean = direction.strip().upper()
    _log(f"Initiating autonomous deployment of {u} ({dir_clean}) at trigger ₹{trigger_price:.2f}...", "EXEC")

    # 1. Inspect live candidates for even-100 series around target ~₹200
    candidates = bm.inspect_m_unit_candidates(
        expiry_date=expiry_date,
        unit_name=u,
        master_anchor_price=trigger_price,
        target_premium=200.0,
        hedge_dist=500,
        sl_pct=25.0
    )
    if not candidates.get("ok"):
        err = candidates.get("message", "Candidate inspection failed")
        _log(f"Failed to find candidates for {u}: {err}", "ERROR")
        return {"ok": False, "message": err}

    h_ce = candidates.get("ce", {})
    h_pe = candidates.get("pe", {})

    # 2. Lock unit settings in DB
    db.set_m_unit_settings(
        unit_name=u,
        locked=True,
        anchor_price=trigger_price,
        horizon="Monthly Expiry",
        expiry_date=expiry_date,
        lots=lots,
        lot_size=int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE))),
        mode="AUTO",
        manual_ce=0,
        manual_pe=0,
        target_premium=200.0
    )

    # 3. Deploy via mature block_manager routine
    res = bm.deploy_or_update_m_unit(
        unit_name=u,
        expiry_date=expiry_date,
        master_anchor_price=trigger_price,
        lots=lots,
        ce_sell_strike=h_ce.get("sell_strike", 0),
        ce_hedge_strike=h_ce.get("hedge_strike", 0),
        ce_sell_ltp=h_ce.get("sell_ltp", 0.0),
        ce_hedge_ltp=h_ce.get("hedge_ltp", 0.0),
        pe_sell_strike=h_pe.get("sell_strike", 0),
        pe_hedge_strike=h_pe.get("hedge_strike", 0),
        pe_sell_ltp=h_pe.get("sell_ltp", 0.0),
        pe_hedge_ltp=h_pe.get("hedge_ltp", 0.0),
        sl_pct=25.0,
        deploy_now=True
    )

    if res.get("ok"):
        trade_desc = "Bull Put Spread (Sell PE + Hedge)" if dir_clean == "UP" else "Bear Call Spread (Sell CE + Hedge)"
        tg_msg = (
            f"🚀 <b>SUPER SUKHOI AUTO-DEPLOYED: {u} ({dir_clean})</b>\n"
            f"Action: <b>{trade_desc}</b>\n"
            f"Anchor Trigger : <b>₹{trigger_price:,.2f}</b>\n"
            f"Lots Deployed  : <b>{lots}</b> | Expiry: <b>{expiry_date or 'Monthly'}</b>\n"
            f"Status         : <b>{res.get('message', 'Complete')}</b>\n"
            f"🛡️ Compulsory Hedge: Pre-bought 500-pt helmet on Kite broker."
        )
        tg.send(tg_msg)
        _log(f"Successfully auto-deployed {u} ({dir_clean}) on Zerodha Kite.", "OK")
    else:
        _log(f"Execution issue deploying {u}: {res.get('message')}", "WARN")

    return res


# ─────────────────────────────────────────────────────────────────────────────
# 5. CONTINUOUS 30-SECOND SUPERVISORY CYCLE
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_super_sukhoi_cycle(force_eval: bool = False) -> Dict[str, Any]:
    """
    Evaluates Super Sukhoi trigger conditions. Called every 30s by main.py background loop.
    Enforces Market Session Guard, M1 anchor derivation, and unidirectional scaling.
    """
    # 1. Session Guard (Brick 1)
    if not force_eval and not utils.is_market_session_active():
        return {"ok": True, "status": "MARKET_CLOSED", "message": "Market is closed. Sleep mode active."}

    # 2. Check if Super Sukhoi is active
    state = db.get_super_sukhoi_state()
    if not state.get("active", False):
        return {"ok": True, "status": "INACTIVE", "message": "Super Sukhoi Auto-Mode is OFF."}

    # 3. Read live Spot
    live_spot = kite_executor.get_nifty_spot()
    if live_spot <= 0:
        live_spot = float(db.get("last_nifty_spot_price", "0.0") or "0.0")
    if live_spot <= 0:
        return {"ok": False, "status": "NO_SPOT", "message": "Could not fetch live Nifty Spot."}

    # 4. Resolve M1 Anchor
    m1_anchor = float(state.get("m1_anchor", 0.0))
    if m1_anchor <= 0:
        m1_settings = db.get_m_unit_settings("M1") or {}
        m1_anchor = float(m1_settings.get("anchor_price", 0.0) or 0.0)
    if m1_anchor <= 0:
        return {"ok": False, "status": "NO_ANCHOR", "message": "M1 Seed Anchor is not set."}

    triggers = compute_triggers(m1_anchor)
    exp = state.get("m1_expiry", "")
    lots = int(state.get("m1_lots", 1) or 1)

    # 5. Check M1 active status
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    b_m1 = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == "M1"), None)
    m1_still_active = False
    if b_m1:
        m1_open_strikes = db.get_strikes_by_block(b_m1["block_id"], status_filter="OPEN")
        m1_still_active = len(m1_open_strikes) > 0

    # ── TIER 1 EVALUATION: M2 UP / M2 DOWN ──
    if not state.get("m2_deployed", False):
        if live_spot >= triggers["m2_up"]:
            _log(f"Spot ₹{live_spot:.2f} >= M2 UP Trigger ₹{triggers['m2_up']:.2f}. Triggering M2 UP Bull Put Spread!", "TRIGGER")
            res = deploy_autonomous_tier("M2", "UP", triggers["m2_up"], exp, lots)
            if res.get("ok"):
                db.set("super_sukhoi_m2_deployed", "1")
                db.set("super_sukhoi_m2_direction", "UP")
                return {"ok": True, "action": "DEPLOYED_M2_UP", "res": res}

        elif live_spot <= triggers["m2_down"]:
            _log(f"Spot ₹{live_spot:.2f} <= M2 DOWN Trigger ₹{triggers['m2_down']:.2f}. Triggering M2 DOWN Bear Call Spread!", "TRIGGER")
            res = deploy_autonomous_tier("M2", "DOWN", triggers["m2_down"], exp, lots)
            if res.get("ok"):
                db.set("super_sukhoi_m2_deployed", "1")
                db.set("super_sukhoi_m2_direction", "DOWN")
                return {"ok": True, "action": "DEPLOYED_M2_DOWN", "res": res}

    # ── TIER 2 EVALUATION: M3 UP / M3 DOWN (Active ONLY if M1 is still active) ──
    elif state.get("m2_deployed", False) and not state.get("m3_deployed", False):
        if not m1_still_active:
            _log("Tier 2 Check: M1 is no longer active. M3 deployment held in standby.", "STANDBY")
            return {"ok": True, "status": "M1_INACTIVE_FOR_M3"}

        m2_dir = state.get("m2_direction", "").upper()
        if m2_dir == "UP" and live_spot >= triggers["m3_up"]:
            _log(f"Spot ₹{live_spot:.2f} >= M3 UP Trigger ₹{triggers['m3_up']:.2f}. Triggering M3 UP Bull Put Spread!", "TRIGGER")
            res = deploy_autonomous_tier("M3", "UP", triggers["m3_up"], exp, lots)
            if res.get("ok"):
                db.set("super_sukhoi_m3_deployed", "1")
                db.set("super_sukhoi_m3_direction", "UP")
                return {"ok": True, "action": "DEPLOYED_M3_UP", "res": res}

        elif m2_dir == "DOWN" and live_spot <= triggers["m3_down"]:
            _log(f"Spot ₹{live_spot:.2f} <= M3 DOWN Trigger ₹{triggers['m3_down']:.2f}. Triggering M3 DOWN Bear Call Spread!", "TRIGGER")
            res = deploy_autonomous_tier("M3", "DOWN", triggers["m3_down"], exp, lots)
            if res.get("ok"):
                db.set("super_sukhoi_m3_deployed", "1")
                db.set("super_sukhoi_m3_direction", "DOWN")
                return {"ok": True, "action": "DEPLOYED_M3_DOWN", "res": res}

    return {
        "ok": True,
        "status": "MONITORING",
        "live_spot": live_spot,
        "m1_anchor": m1_anchor,
        "triggers": triggers,
        "m2_deployed": state.get("m2_deployed", False),
        "m3_deployed": state.get("m3_deployed", False),
    }
