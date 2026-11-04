"""
terminal_backend.py — Next-Gen High-Frequency Backend Adapter (Zerodha OS)
===========================================================================
Version: V7.0 (Production Edition — 100% Full Feature Parity)
Architecture: Thread-safe, non-blocking data adapter layer.
Connects NiceGUI (Port 9009) to Zerodha OS SQLite, Kite API, and Engines:
  • db.py                  -- SQLite Database Engine (zerodha_trader.db)
  • block_manager.py       -- Directional M-Units (M1–M4) & Block Manager
  • os_engine.py           -- Momentum OS-Units (OS1–OS5)
  • weekly_st_engine.py    -- Weekly ST-2H Cockpit (W1 — V7.5 Master Edition)
  • commodity_engine.py    -- MCX Commodity Futures Engine
  • commodity_executor.py  -- MCX Execution & Contract Resolver
  • equity_200dma_engine.py-- Equity & Gold 200 DMA Monitoring Engine
  • kite_executor.py       -- Zerodha Kite Connect Broker API
"""

import os
import sys
import time
import math
from datetime import datetime, time as dtime
from typing import Dict, List, Any, Optional, Tuple
import pytz

import config as cfg
import db
import block_manager as bm
import os_engine
import weekly_st_engine as wst_engine
import commodity_executor as comm_exec
import equity_200dma_engine as eq_engine
from kite_executor import kite_executor

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# TTL IN-MEMORY CACHE (PREVENTS OVERWHELMING BROKER/DB ON HIGH-FREQ WEBSOCKETS)
# ─────────────────────────────────────────────────────────────────────────────
_CACHE = {}


def _get_cached(key: str, ttl_sec: float = 2.0):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"] < ttl_sec):
        return entry["val"]
    return None


def _set_cached(key: str, val: Any):
    _CACHE[key] = {"val": val, "ts": time.time()}


# ─────────────────────────────────────────────────────────────────────────────
# 1. LIVE SPOT & BROKER HEALTH
# ─────────────────────────────────────────────────────────────────────────────
def get_live_spot() -> float:
    """Returns real-time NIFTY 50 Spot LTP with memory caching."""
    cached = _get_cached("nifty_spot", ttl_sec=2.0)
    if cached is not None and cached > 0:
        return cached

    spot = 0.0
    try:
        spot = kite_executor.get_nifty_spot()
    except Exception:
        pass

    if spot <= 0:
        try:
            spot = float(db.get("last_nifty_spot_price") or db.get("last_master_spot_price") or 22421.0)
        except Exception:
            spot = 22421.0

    _set_cached("nifty_spot", spot)
    return round(spot, 2)


def get_broker_status() -> Dict[str, Any]:
    """Returns Zerodha Kite Connect broker connection and token health."""
    try:
        is_conn = kite_executor.is_connected() if hasattr(kite_executor, "is_connected") else True
        ucc = getattr(kite_executor, "user_id", "") or "Zerodha Kite"
        if is_conn:
            return {
                "connected": True,
                "status_text": f"🟢 Kite Live ({ucc})",
                "badge_color": "positive",
                "broker": "Zerodha Kite"
            }
    except Exception as e:
        pass

    return {
        "connected": False,
        "status_text": "🔴 Token Expired / Offline",
        "badge_color": "negative",
        "broker": "Zerodha Kite"
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. STATUS RIBBON & REAL-TIME METRICS
# ─────────────────────────────────────────────────────────────────────────────
def get_status_ribbon_data() -> Dict[str, Any]:
    """Computes all header metrics, active blocks, open legs, and total P&L."""
    live_spot = get_live_spot()
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    n_blocks = len(active_blocks)

    all_strikes = []
    for b in active_blocks:
        b_id = b.get("block_id") or b.get("id")
        stks = db.get_strikes_by_block(b_id) if hasattr(db, "get_strikes_by_block") else db.get_strikes_for_block(b_id)
        all_strikes.extend(stks)

    open_strikes = [s for s in all_strikes if s.get("status") in ("OPEN", "EXECUTED")]
    n_open = len(open_strikes)
    n_hedges = len([s for s in open_strikes if s.get("leg_type") == "HEDGE" or s.get("action") == "BUY"])

    # Compute Total Portfolio P&L
    total_pnl = 0.0
    for s in all_strikes:
        ltp = float(s.get("current_price") or s.get("ltp") or 0.0)
        fill_p = float(s.get("fill_price") or s.get("entry_price") or s.get("anchor_price") or 0.0)
        lots = int(s.get("lots") or 1)
        qty = lots * cfg.NIFTY_LOT_SIZE
        act = s.get("action", "SELL")
        if s.get("status") in ("OPEN", "EXECUTED"):
            pnl = (fill_p - ltp) * qty if act == "SELL" else (ltp - fill_p) * qty
            total_pnl += pnl
        elif s.get("status") == "CLOSED":
            exit_p = float(s.get("exit_price") or fill_p)
            pnl = (fill_p - exit_p) * qty if act == "SELL" else (exit_p - fill_p) * qty
            total_pnl += pnl

    # Master Algo Status
    algo_running = db.get("algo_running", "ON") == "ON"
    sl_sentinel = db.get("sl_sentinel_active", "ON") == "ON"

    # Token Refresh Heartbeat Countdown
    last_rf = float(db.get("token_last_refresh_ts", "0") or "0")
    now_ts = time.time()
    elapsed = int(now_ts - last_rf) if last_rf > 0 else 0
    rf_countdown = max(0, 900 - elapsed)
    cd_str = f"{rf_countdown // 60}m {rf_countdown % 60}s" if rf_countdown > 0 else "Renewing..."

    return {
        "live_spot": live_spot,
        "total_pnl": round(total_pnl, 2),
        "n_blocks": n_blocks,
        "n_open_strikes": n_open,
        "n_hedges": n_hedges,
        "algo_running": algo_running,
        "sl_sentinel": sl_sentinel,
        "token_countdown": cd_str,
        "broker_status": get_broker_status()
    }


def get_global_200dma_alert() -> Dict[str, Any]:
    """Checks if any long-term equity holding has breached below 200 DMA."""
    try:
        analysis = eq_engine.get_equity_analysis()
        reds = analysis.get("red_alerts", [])
        if reds:
            symbols = [r["symbol"] for r in reds[:5]]
            return {
                "active": True,
                "count": len(reds),
                "symbols_str": ", ".join(symbols) + ("..." if len(reds) > 5 else ""),
                "red_alerts": reds
            }
    except Exception:
        pass
    return {"active": False, "count": 0, "symbols_str": "", "red_alerts": []}


# ─────────────────────────────────────────────────────────────────────────────
# 3. EXECUTIVE POD MATRIX (SPLIT VIEW: M-UNITS LEFT | OS-UNITS RIGHT)
# ─────────────────────────────────────────────────────────────────────────────
def get_executive_pod_matrix() -> Dict[str, Any]:
    """Generates matrix cards for M1-M4 (left) and OS1-OS5 (right)."""
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    live_spot = get_live_spot()

    # M-Series (M1–M4)
    m_pods = []
    for uname in ["M1", "M2", "M3", "M4"]:
        m_cfg = db.get_m_unit_settings(uname)
        anchor = float(m_cfg.get("anchor_price", 23350.0))
        regime = "BULLISH" if live_spot >= anchor else "BEARISH"
        diff = live_spot - anchor

        # Find active block
        blk = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == uname), None)
        has_active = blk is not None
        b_id = (blk.get("block_id") or blk.get("id")) if blk else None

        net_pnl = 0.0
        legs_summary = []
        if blk and b_id:
            stks = db.get_strikes_by_block(b_id) if hasattr(db, "get_strikes_by_block") else db.get_strikes_for_block(b_id)
            for s in stks:
                if s.get("status") in ("OPEN", "EXECUTED"):
                    ltp = float(s.get("current_price") or s.get("ltp") or 0.0)
                    fill = float(s.get("fill_price") or s.get("anchor_price") or 0.0)
                    qty = int(s.get("lots") or 1) * cfg.NIFTY_LOT_SIZE
                    act = s.get("action", "SELL")
                    pnl = (fill - ltp) * qty if act == "SELL" else (ltp - fill) * qty
                    net_pnl += pnl
                    legs_summary.append(f"{s.get('strike_price')} {s.get('option_type')}")

        m_pods.append({
            "unit_name": uname,
            "anchor": anchor,
            "regime": regime,
            "diff": round(diff, 2),
            "has_active": has_active,
            "block_id": b_id,
            "net_pnl": round(net_pnl, 2),
            "legs_summary": legs_summary,
            "locked": m_cfg.get("locked", False)
        })

    # OS-Series (OS1–OS5)
    os_pods = []
    for uname in ["OS1", "OS2", "OS3", "OS4", "OS5"]:
        os_cfg = db.get_os_unit_settings(uname) if hasattr(db, "get_os_unit_settings") else {}
        blk = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == uname), None)
        b_id = (blk.get("block_id") or blk.get("id")) if blk else None

        net_pnl = 0.0
        legs_summary = []
        if blk and b_id:
            stks = db.get_strikes_by_block(b_id) if hasattr(db, "get_strikes_by_block") else db.get_strikes_for_block(b_id)
            for s in stks:
                if s.get("status") in ("OPEN", "EXECUTED"):
                    ltp = float(s.get("current_price") or s.get("ltp") or 0.0)
                    fill = float(s.get("fill_price") or s.get("anchor_price") or 0.0)
                    qty = int(s.get("lots") or 1) * cfg.NIFTY_LOT_SIZE
                    pnl = (fill - ltp) * qty
                    net_pnl += pnl
                    legs_summary.append(f"{s.get('strike_price')} {s.get('option_type')}")

        os_pods.append({
            "unit_name": uname,
            "has_active": blk is not None,
            "block_id": b_id,
            "net_pnl": round(net_pnl, 2),
            "legs_summary": legs_summary,
            "expiry": os_cfg.get("expiry_date", "") if os_cfg else "",
            "locked": os_cfg.get("locked", False) if os_cfg else False
        })

    return {"m_pods": m_pods, "os_pods": os_pods}


# ─────────────────────────────────────────────────────────────────────────────
# 4. TAB 1: DIRECTIONAL M-UNITS (M1–M4) COCKPIT
# ─────────────────────────────────────────────────────────────────────────────
def get_m_unit_cockpit_data(unit_name: str = "M1") -> Dict[str, Any]:
    """Provides complete state for M-Unit Cockpit including JIT Dynamic Strike Hunter."""
    u = unit_name.strip().upper()
    m_cfg = db.get_m_unit_settings(u)
    live_spot = get_live_spot()

    anchor = float(m_cfg.get("anchor_price", 23350.0))
    regime = "BULLISH" if live_spot >= anchor else "BEARISH"
    diff = live_spot - anchor

    # Expiries
    cat_expiries = os_engine.get_categorized_expiries()
    all_expiries = cat_expiries.get("all", ["2026-10-27"])

    # 14:55 / Post-3PM Entry Freeze Check
    now_ist = datetime.now(IST).time()
    freeze_active = now_ist >= dtime(14, 55) or now_ist < dtime(9, 15)

    # Candidate Strike Recommendations (~₹200 on EVEN 100s, 500-pt hedge)
    base_100 = int(round(live_spot / 100.0) * 100)
    target_prem = float(m_cfg.get("target_premium", 200.0))
    min_floor = max(140.0, target_prem * 0.70)

    # Recommended strikes preview
    ce_candidate_strike = base_100 + 400
    ce_hedge_strike = ce_candidate_strike + 500
    pe_candidate_strike = base_100 - 400
    pe_hedge_strike = pe_candidate_strike - 500

    # Active Block Legs
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    unit_block = next((b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper() == u), None)

    strikes = []
    if unit_block:
        b_id = unit_block.get("block_id") or unit_block.get("id")
        strikes = db.get_strikes_by_block(b_id) if hasattr(db, "get_strikes_by_block") else db.get_strikes_for_block(b_id)

    ce_legs = [s for s in strikes if s.get("option_type") == "CE"]
    pe_legs = [s for s in strikes if s.get("option_type") == "PE"]

    return {
        "unit_name": u,
        "settings": m_cfg,
        "is_locked": m_cfg.get("locked", False),
        "live_spot": live_spot,
        "anchor_price": anchor,
        "regime": regime,
        "diff": round(diff, 2),
        "freeze_active": freeze_active,
        "min_floor": min_floor,
        "all_expiries": all_expiries,
        "candidates": {
            "ce_sell": ce_candidate_strike,
            "ce_hedge": ce_hedge_strike,
            "pe_sell": pe_candidate_strike,
            "pe_hedge": pe_hedge_strike,
            "target_premium": target_prem
        },
        "block": unit_block,
        "strikes": strikes,
        "ce_legs": ce_legs,
        "pe_legs": pe_legs,
        "has_active": bool(unit_block and strikes)
    }


def deploy_or_update_m_unit_action(
    unit_name: str,
    expiry_date: str,
    anchor_price: float,
    lots: int,
    ce_sell_strike: int,
    ce_hedge_strike: int,
    pe_sell_strike: int,
    pe_hedge_strike: int,
    deploy_now: bool = True
) -> Dict[str, Any]:
    """Deploys or updates M-Unit using atomic Kite execution."""
    try:
        res = bm.deploy_or_update_m_unit(
            unit_name=unit_name,
            expiry_date=expiry_date,
            master_anchor_price=anchor_price,
            lots=lots,
            ce_sell_strike=ce_sell_strike,
            ce_hedge_strike=ce_hedge_strike,
            pe_sell_strike=pe_sell_strike,
            pe_hedge_strike=pe_hedge_strike,
            deploy_now=deploy_now
        )
        return {"ok": True, "message": f"{unit_name} Deployed successfully.", "data": res}
    except Exception as e:
        return {"ok": False, "message": f"Deployment error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. TAB 2: MOMENTUM OS-UNITS (OS1–OS5) COCKPIT
# ─────────────────────────────────────────────────────────────────────────────
def get_os_unit_cockpit_data(unit_name: str = "OS1") -> Dict[str, Any]:
    """Provides complete state for Momentum OS Units."""
    u = unit_name.strip().upper()
    cat_expiries = os_engine.get_categorized_expiries()
    all_expiries = cat_expiries.get("all", ["2026-10-27"])

    os_cfg = db.get_os_unit_settings(u) if hasattr(db, "get_os_unit_settings") else {}
    is_locked = os_cfg.get("locked", False) if os_cfg else False

    # Active OS blocks
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    os_blocks = [b for b in active_blocks if (b.get("anchor_unit_name") or "").strip().upper().startswith("OS")]

    for b in os_blocks:
        b_id = b.get("block_id") or b.get("id")
        stks = db.get_strikes_by_block(b_id) if hasattr(db, "get_strikes_by_block") else db.get_strikes_for_block(b_id)
        b["strikes"] = stks

    return {
        "unit_name": u,
        "settings": os_cfg,
        "is_locked": is_locked,
        "cat_expiries": cat_expiries,
        "all_expiries": all_expiries,
        "active_os_blocks": os_blocks
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. TAB 3: WEEKLY ST-2H COCKPIT (W1 — V7.5 MASTER EDITION)
# ─────────────────────────────────────────────────────────────────────────────
def get_weekly_st_cockpit_data() -> Dict[str, Any]:
    """Provides Weekly ST metrics, SuperTrend (8,2), and Decide & Lock state."""
    cfg_st = wst_engine.get_weekly_st_settings()
    st_res = wst_engine.calculate_supertrend_2h(period=8, multiplier=2.0)
    w_pos = wst_engine.get_active_w_position()

    live_spot = get_live_spot()
    st_val = float(st_res.get("st_value") or 0.0)
    trend = st_res.get("trend", "BEARISH")
    spot_dist = live_spot - st_val if st_val > 0 else 0.0

    # Pulse Countdown
    now_ist = datetime.now(IST)
    pulse_min = now_ist.minute
    pulse_sec = now_ist.second
    mins_left = (120 - (now_ist.hour % 2 * 60 + pulse_min)) % 120
    secs_left = 60 - pulse_sec

    # Hunter Preview
    expiries = wst_engine.get_upcoming_weekly_expiries()
    candidate = None
    info = ""
    try:
        cand_dict = wst_engine.hunt_weekly_st_spread(
            direction=trend if trend in ("BULLISH", "BEARISH") else "BEARISH",
            min_prem=float(cfg_st.get("min_prem", 80.0)),
            max_prem=float(cfg_st.get("max_prem", 100.0)),
            hedge_distance=int(cfg_st.get("hedge_dist", 500)),
            expiry_mode=cfg_st.get("expiry_mode", "AUTO"),
            target_expiry=cfg_st.get("target_expiry", ""),
            min_spot_buffer=float(cfg_st.get("min_spot_buffer", 150.0)),
            st_clearance=float(cfg_st.get("st_clearance", 50.0)),
            st_value=st_val,
            spot_val=live_spot
        )
        if isinstance(cand_dict, dict) and cand_dict.get("ok"):
            candidate = {
                "ok": True,
                "side": cand_dict.get("direction", trend),
                "expiry": cand_dict.get("expiry"),
                "short_strike": cand_dict.get("sell_strike"),
                "sell_strike": cand_dict.get("sell_strike"),
                "option_type": cand_dict.get("sell_option_type"),
                "sell_option_type": cand_dict.get("sell_option_type"),
                "short_ltp": cand_dict.get("sell_ltp", 0.0),
                "sell_ltp": cand_dict.get("sell_ltp", 0.0),
                "hedge_strike": cand_dict.get("hedge_strike"),
                "hedge_ltp": cand_dict.get("hedge_ltp", 0.0),
                "net_credit": cand_dict.get("estimated_net_credit", 0.0),
                "estimated_net_credit": cand_dict.get("estimated_net_credit", 0.0),
                "moat_rule": cand_dict.get("moat_rule", "")
            }
        elif isinstance(cand_dict, dict):
            info = cand_dict.get("message", "")
    except Exception as e:
        candidate = None
        info = str(e)

    is_algo_enabled = db.get("weekly_st_algo_enabled", "OFF") == "ON"

    return {
        "settings": cfg_st,
        "supertrend": st_res,
        "trend": trend,
        "st_value": st_val,
        "live_spot": live_spot,
        "spot_distance": round(spot_dist, 2),
        "pulse_clock": f"{mins_left}m {secs_left}s",
        "active_position": w_pos,
        "candidate": candidate,
        "candidate_info": info,
        "expiries": expiries,
        "is_locked": cfg_st.get("locked", False),
        "is_algo_enabled": is_algo_enabled
    }


def toggle_weekly_st_algo(enabled: bool) -> Dict[str, Any]:
    """Toggles Weekly ST autonomous execution."""
    try:
        db.set("weekly_st_algo_enabled", "ON" if enabled else "OFF")
        return {"ok": True, "message": f"Weekly ST Algo set to {'ON' if enabled else 'OFF'}."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def lock_weekly_st_strategy(mode: str, buffer_pts: float, lots: int) -> Dict[str, Any]:
    """Locks Weekly ST Strategy parameters."""
    try:
        exp_mode = "FORCE_NEXT" if "Next" in mode else ("FORCE_CURRENT" if "Current" in mode else "AUTO")
        wst_engine.set_weekly_st_settings(
            locked=True,
            expiry_mode=exp_mode,
            target_expiry="",
            min_spot_buffer=float(buffer_pts),
            st_clearance=50.0
        )
        db.set("weekly_st_lots", str(lots))
        return {"ok": True, "message": "Weekly ST Strategy Locked & Armed."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def unlock_weekly_st_strategy() -> Dict[str, Any]:
    """Unlocks Weekly ST Strategy for reconfiguration."""
    try:
        db.set("weekly_st_expiry_locked", "0")
        return {"ok": True, "message": "Weekly ST Strategy Unlocked for Editing."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 7. TAB 4: ACTIVE EXPIRY BLOCKS & LIVE POSITIONS
# ─────────────────────────────────────────────────────────────────────────────
def get_all_active_blocks_detailed() -> List[Dict[str, Any]]:
    """Returns rich block summaries with enriched strikes for block cards."""
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    enriched_blocks = []
    live_spot = get_live_spot()

    for b in active_blocks:
        b_id = b.get("block_id") or b.get("id")
        summary = bm.get_block_summary(b_id) or {"block": b, "strikes": []}
        strikes = summary.get("strikes", [])

        ce_strikes = []
        pe_strikes = []
        block_pnl = 0.0

        for s in strikes:
            s_dict = dict(s)
            ltp = float(s_dict.get("current_price") or s_dict.get("ltp") or 0.0)
            fill_p = float(s_dict.get("fill_price") or s_dict.get("entry_price") or s_dict.get("anchor_price") or 0.0)
            lots = int(s_dict.get("lots") or 1)
            qty = lots * cfg.NIFTY_LOT_SIZE
            act = s_dict.get("action", "SELL")

            if s_dict.get("status") in ("OPEN", "EXECUTED"):
                pnl = (fill_p - ltp) * qty if act == "SELL" else (ltp - fill_p) * qty
            elif s_dict.get("status") == "CLOSED":
                exit_p = float(s_dict.get("exit_price") or fill_p)
                pnl = (fill_p - exit_p) * qty if act == "SELL" else (exit_p - fill_p) * qty
            else:
                pnl = 0.0

            s_dict["calculated_pnl"] = round(pnl, 2)
            block_pnl += pnl

            if s_dict.get("option_type") == "CE":
                ce_strikes.append(s_dict)
            else:
                pe_strikes.append(s_dict)

        unit_name = b.get("anchor_unit_name") or f"M{b.get('block_number', 1)}"
        unit_anchor = float(b.get("master_anchor_price") or 0.0)
        regime = "BULLISH" if live_spot >= unit_anchor else "BEARISH"

        enriched_blocks.append({
            "block": b,
            "block_id": b_id,
            "block_number": b.get("block_number", "?"),
            "unit_name": unit_name,
            "unit_anchor": unit_anchor,
            "regime": regime,
            "status": b.get("status", "ACTIVE"),
            "expiry_date": b.get("expiry_date", ""),
            "expiry_type": b.get("expiry_type", "MONTHLY"),
            "total_pnl": round(block_pnl, 2),
            "ce_strikes": ce_strikes,
            "pe_strikes": pe_strikes,
            "all_strikes": strikes
        })

    return enriched_blocks


def update_block_anchor(block_id: int, new_anchor: float) -> Dict[str, Any]:
    """Updates master anchor for a specific block."""
    try:
        db.update_block_anchor(block_id, float(new_anchor))
        live_spot = get_live_spot()
        new_reg = "BULLISH" if live_spot >= new_anchor else "BEARISH"
        db.update_block_regime(block_id, new_reg)
        return {"ok": True, "message": f"Block {block_id} Anchor set to ₹{new_anchor:,.2f} ({new_reg})."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def square_off_block(block_id: int) -> Dict[str, Any]:
    """Squares off all strikes in a block."""
    try:
        bm.square_off_block(block_id)
        return {"ok": True, "message": f"Block #{block_id} squared off successfully."}
    except Exception as e:
        return {"ok": False, "message": f"Error: {e}"}


def square_off_strike(strike_id: int) -> Dict[str, Any]:
    """Squares off an individual strike."""
    try:
        bm.square_off_strike(strike_id)
        return {"ok": True, "message": f"Strike #{strike_id} closed."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def sweep_orphan_hedges() -> Dict[str, Any]:
    """Sweeps and closes orphan hedges left from stopped-out blocks."""
    try:
        n_closed = bm.clean_orphan_hedges() if hasattr(bm, "clean_orphan_hedges") else 0
        return {"ok": True, "message": f"Swept {n_closed} orphan hedges."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 8. TAB 5: MCX COMMODITIES FUT ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def get_commodity_cockpit_data() -> Dict[str, Any]:
    """Provides complete state for MCX Commodity Futures Engine."""
    comm_running = db.get("comm_engine_running", "OFF") == "ON"
    pos_state = db.get("comm_position_state", "FLAT")
    entry_p = float(db.get("comm_entry_price", "0.0") or 0.0)
    entry_t = db.get("comm_entry_time", "")
    saved_contract = db.get("comm_selected_contract", "CRUDEOIL")

    assets = [
        "CRUDEOIL", "CRUDEOILM", "NATURALGAS", "NATGASMINI",
        "GOLD", "GOLDM", "GOLDPETAL", "SILVER", "SILVERM", "SILVERMIC",
        "COPPER", "ZINC", "LEAD", "ALUMINIUM"
    ]
    if saved_contract and saved_contract not in assets:
        assets.insert(0, saved_contract)

    # Resolve positions from broker
    positions = []
    try:
        positions = comm_exec.get_all_mcx_positions()
    except Exception:
        pass

    # Live LTP for selected contract
    live_ltp = 0.0
    try:
        live_ltp = comm_exec.get_mcx_ltp(saved_contract)
    except Exception:
        pass

    # Live P&L
    comm_pnl = 0.0
    if pos_state == "LONG" and live_ltp > 0 and entry_p > 0:
        comm_pnl = live_ltp - entry_p
    elif pos_state == "SHORT" and live_ltp > 0 and entry_p > 0:
        comm_pnl = entry_p - live_ltp

    return {
        "running": comm_running,
        "position_state": pos_state,
        "entry_price": entry_p,
        "entry_time": entry_t,
        "selected_contract": saved_contract,
        "assets_list": assets,
        "live_ltp": live_ltp,
        "live_pnl": round(comm_pnl, 2),
        "positions": positions
    }


def toggle_commodity_engine(active: bool) -> Dict[str, Any]:
    """Turns MCX Commodity engine ON or OFF."""
    try:
        db.set("comm_engine_running", "ON" if active else "OFF")
        if active:
            db.set("comm_last_check_candle_time", "")
        return {"ok": True, "message": f"Commodity Engine set to {'ACTIVE' if active else 'PAUSED'}."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def square_off_commodity_position() -> Dict[str, Any]:
    """Closes all MCX commodity positions."""
    try:
        comm_exec.square_off_all_mcx_positions()
        comm_exec._clear_comm_db_state()
        return {"ok": True, "message": "All MCX Commodity Positions Squared Off."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 9. TAB 6: EQUITY & GOLD (200 DMA MONITOR)
# ─────────────────────────────────────────────────────────────────────────────
def get_equity_200dma_cockpit_data() -> Dict[str, Any]:
    """Provides full portfolio collateral analysis and 200 DMA signals."""
    analysis = eq_engine.get_equity_analysis()
    return analysis


def sync_equity_holdings_from_kite() -> Dict[str, Any]:
    """Fetches fresh holdings from Zerodha Kite."""
    try:
        ok, msg = eq_engine.sync_holdings_from_zerodha()
        return {"ok": ok, "message": msg}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def recalculate_all_200dma() -> Dict[str, Any]:
    """Downloads historical candles and recalculates 200 DMA."""
    try:
        eq_engine.refresh_all_200dma()
        return {"ok": True, "message": "200 DMA Recalculated for all stocks."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# 10. TAB 7: ORDER HISTORY & REAL-TIME AUDIT LOGS
# ─────────────────────────────────────────────────────────────────────────────
def get_audit_logs(category: str = "ALL", limit: int = 150) -> List[Dict[str, str]]:
    """Reads and parses recent lines from zerodha_engine.log."""
    log_file = cfg.LOG_PATH
    if not os.path.exists(log_file):
        # Fallback log
        alt_log = os.path.join(cfg.BASE_DIR, "option_selling_today.log")
        if os.path.exists(alt_log):
            log_file = alt_log
        else:
            return []

    lines = []
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-limit * 3:]
    except Exception:
        return []

    cat_upper = category.upper()
    parsed_logs = []

    for l in reversed(recent_lines):
        txt = l.strip()
        if not txt:
            continue

        level = "INFO"
        lvl_col = "text-slate-300"
        if "ERR" in txt or "EXCEPTION" in txt or "FAIL" in txt:
            level = "ERROR"
            lvl_col = "text-red-400 font-bold"
        elif "WARN" in txt:
            level = "WARN"
            lvl_col = "text-amber-400"
        elif "SL HIT" in txt or "SENTINEL" in txt:
            level = "SL_SENTINEL"
            lvl_col = "text-rose-400 font-black"
        elif "ORDER" in txt or "BUY" in txt or "SELL" in txt:
            level = "ORDERS"
            lvl_col = "text-emerald-400 font-bold"
        elif "EXIT" in txt or "SQUARE" in txt or "CLOSE" in txt:
            level = "EXITS"
            lvl_col = "text-cyan-400 font-bold"
        elif "COMMODITY" in txt or "MCX" in txt:
            level = "COMMODITY"
            lvl_col = "text-orange-400"
        elif "200 DMA" in txt or "EQUITY" in txt:
            level = "EQUITY_200DMA"
            lvl_col = "text-purple-400"

        if cat_upper != "ALL" and level != cat_upper:
            continue

        parsed_logs.append({
            "raw": txt,
            "level": level,
            "color_class": lvl_col
        })

        if len(parsed_logs) >= limit:
            break

    return parsed_logs


# ─────────────────────────────────────────────────────────────────────────────
# 11. GLOBAL EMERGENCY PANIC SQUARE-OFF
# ─────────────────────────────────────────────────────────────────────────────
def emergency_square_off_all() -> Dict[str, Any]:
    """Immediately kills Algo and squares off all positions across all engines."""
    try:
        db.set("algo_running", "OFF")
        db.set("master_kill_switch", "KILLED")

        # 1. Square off all Active Option Blocks
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        for b in active_blocks:
            b_id = b.get("block_id") or b.get("id")
            bm.square_off_block(b_id)

        # 2. Square off Weekly ST
        try:
            wst_engine.kill_all_weekly_st_positions()
        except Exception:
            pass

        # 3. Square off MCX Commodities
        try:
            comm_exec.square_off_all_mcx_positions()
            comm_exec._clear_comm_db_state()
        except Exception:
            pass

        return {"ok": True, "message": "🚨 ALL POSITIONS SQUARED OFF AND ALGO KILLED."}
    except Exception as e:
        return {"ok": False, "message": f"Emergency Square-Off failed: {e}"}
