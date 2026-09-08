"""
block_manager.py -- Zerodha OptionSelling Engine | Brick 3
=========================================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 3)
Date     : June 2026

THE CORE LOGIC BRAIN of the engine.
Orchestrates: Block creation -> Strike setup -> Execution -> Close

Responsibilities:
  - Create / view / delete blocks (one expiry per block)
  - Add CE/PE sell + hedge_buy strikes to a block
  - Link hedge strikes to their sell strikes (paired)
  - Execute a block: place all orders via kite_executor
  - Execute a single strike (sell + its hedge together)
  - Close a strike + its paired hedge (HARD RULE: always together)
  - Archive expired blocks (status -> EXPIRED)
  - Return full block summary for dashboard

HARD RULES enforced here (per Blueprint):
  1. NIFTY ONLY -- enforced at executor level
  2. Max strikes per block -- enforced at db level (configurable)
  3. One expiry per block -- enforced here
  4. Close = Sell strike + Hedge together -- HARD RULE
  5. Anchor price = manual (never auto) -- enforced at db level
  6. No block delete if any strike OPEN -- enforced at db level
  7. Entry sequence: BUY hedge FIRST, then SELL option
"""

import sys
import time
import threading
from typing import Optional

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg
from kite_executor import kite_executor
import telegram_bot as tg

# ─────────────────────────────────────────────────────────────────────────────
# Internal logger
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = "INFO") -> None:
    print(f"[BLOCK_MGR][{level}] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCK OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def create_block(
    expiry_date: str,
    expiry_type: str = "MONTHLY",
    side_type: str = "BOTH",
    notes: str = "",
    anchor_unit_name: str = "",
    master_anchor_price: float = 0.0,
    regime_buffer: float = 15.0,
    custom_lots: int = 2,
    current_regime: str = "NEUTRAL",
    recommended_lots: int = 1,
    anchor_decision_time: str = "15:00",
    orphan_hedge_policy: str = "PRESERVE",
    auto_regime_enabled: int = 1,
    **kwargs
) -> dict:
    """
    Creates a new trading block (V3.0 Autonomous Multi-Anchor Unit).

    Supports side_type: 'CALL', 'PUT', or 'BOTH'.
    Allows multiple independent units (M1, M2, M3...) for the SAME expiry date.

    expiry_date         : "26-Jun-2025" (DD-Mon-YYYY format)
    expiry_type         : "MONTHLY" or "WEEKLY"
    side_type           : "CALL", "PUT", or "BOTH"
    notes               : Optional user label
    anchor_unit_name    : Unit identifier (e.g. "M1", "M2", "M3")
    master_anchor_price : Dedicated unit anchor (0.0 = unset)
    regime_buffer       : Hysteresis buffer (default 15.0 pts)

    Returns: {"ok": bool, "block_id": int, "block_number": int, "message": str}
    """
    # Normalize inputs
    expiry_date = expiry_date.strip()
    expiry_type = expiry_type.upper()
    side_type   = side_type.strip().upper()

    if expiry_type not in ("MONTHLY", "WEEKLY"):
        return {"ok": False, "message": f"Invalid expiry_type '{expiry_type}'. Must be MONTHLY or WEEKLY."}
    if side_type not in ("CALL", "PUT", "BOTH"):
        side_type = "BOTH"

    unit_name = str(anchor_unit_name).strip().upper() if anchor_unit_name else "M1"


    # Check for duplicate ACTIVE block with matching side/expiry AND SAME UNIT NAME
    existing_blocks = db.get_all_blocks(status_filter="ACTIVE")
    for b in existing_blocks:
        b_exp  = b["expiry_date"].strip().upper()
        b_side = (b.get("side_type") or "BOTH").strip().upper()
        b_unit = (b.get("anchor_unit_name") or "M1").strip().upper()

        if b_exp == expiry_date.upper() and b_unit == unit_name:
            if side_type == "BOTH" or b_side == "BOTH" or b_side == side_type:
                _log(
                    f"DUPLICATE BLOCKED: ACTIVE Unit {b_unit} Block #{b['block_number']} ({b_side}) already exists for expiry {expiry_date}.",
                    "WARN"
                )
                return {
                    "ok":           False,
                    "block_id":     b["block_id"],
                    "block_number": b["block_number"],
                    "message":      f"Unit {b_unit} Block #{b['block_number']} ({b_side}) already exists for expiry {expiry_date}. Choose a new Unit name (e.g. {db.get_next_unit_name(expiry_date)}) for fresh blocks.",
                    "duplicate":    True,
                }

    block_id = db.create_block(
        expiry_date=expiry_date,
        expiry_type=expiry_type,
        side_type=side_type,
        notes=notes,
        anchor_unit_name=unit_name,
        master_anchor_price=master_anchor_price,
        regime_buffer=regime_buffer,
        custom_lots=custom_lots,
        current_regime=current_regime,
        auto_regime_enabled=auto_regime_enabled,
        anchor_decision_time=anchor_decision_time,
        recommended_lots=recommended_lots,
        orphan_hedge_policy=orphan_hedge_policy
    )
    if block_id < 0:
        return {"ok": False, "message": "DB error creating block."}

    block = db.get_block(block_id)
    _log(f"Block #{block['block_number']} [Unit {unit_name}] created | Anchor: ₹{master_anchor_price:,.2f} | Expiry: {expiry_date} ({expiry_type}) | Side: {side_type}", "OK")
    return {
        "ok":           True,
        "block_id":     block_id,
        "block_number": block["block_number"],
        "unit_name":    unit_name,
        "message":      f"Block #{block['block_number']} [Unit {unit_name}] ({side_type}) created for {expiry_date} ({expiry_type}).",
    }


def create_separate_blocks(
    expiry_date: str,
    expiry_type: str = "MONTHLY",
    notes: str = "",
    anchor_unit_name: str = "",
    master_anchor_price: float = 0.0,
    regime_buffer: float = 15.0,
    custom_lots: int = 2
) -> dict:
    """
    Creates separate CALL and PUT blocks for the same expiry date under a given Unit in one atomic action.
    """
    unit_name = str(anchor_unit_name).strip().upper() if anchor_unit_name else ""
    if not unit_name:
        unit_name = db.get_next_unit_name(expiry_date)

    call_note = f"{notes} (Call Side)".strip() if notes else f"Unit {unit_name} Call Side"
    put_note  = f"{notes} (Put Side)".strip() if notes else f"Unit {unit_name} Put Side"

    res_call = create_block(
        expiry_date=expiry_date,
        expiry_type=expiry_type,
        side_type="CALL",
        notes=call_note,
        anchor_unit_name=unit_name,
        master_anchor_price=master_anchor_price,
        regime_buffer=regime_buffer,
        custom_lots=custom_lots
    )
    res_put  = create_block(
        expiry_date=expiry_date,
        expiry_type=expiry_type,
        side_type="PUT",
        notes=put_note,
        anchor_unit_name=unit_name,
        master_anchor_price=master_anchor_price,
        regime_buffer=regime_buffer,
        custom_lots=custom_lots
    )

    if res_call["ok"] and res_put["ok"]:
        return {
            "ok": True,
            "unit_name": unit_name,
            "call_block_id": res_call["block_id"],
            "put_block_id": res_put["block_id"],
            "message": f"Created Unit {unit_name} (2 blocks) for {expiry_date}: Block #{res_call['block_number']} (CALL) and Block #{res_put['block_number']} (PUT)."
        }
    else:
        errs = []
        if res_call["ok"]:
            errs.append(f"Block #{res_call['block_number']} (CALL) created.")
        else:
            errs.append(f"CALL: {res_call['message']}")
        if res_put["ok"]:
            errs.append(f"Block #{res_put['block_number']} (PUT) created.")
        else:
            errs.append(f"PUT: {res_put['message']}")
        return {"ok": res_call["ok"] or res_put["ok"], "message": " | ".join(errs)}


# ─────────────────────────────────────────────────────────────────────────────
# V5.0 "OLD & GOLD" UNIFIED SINGLE-WINDOW DEPLOYMENT & ORPHAN HEDGE CONTROL
# ─────────────────────────────────────────────────────────────────────────────

def deploy_unified_master_unit(
    expiry_date: str,
    anchor_unit_name: str = "M1",
    master_anchor_price: float = 0.0,
    regime_buffer: float = 15.0,
    recommended_lots: int = 1,
    notes: str = "",
    # Call wing
    ce_sell_strike: int = 0,
    ce_sell_anchor: float = 0.0,
    ce_hedge_strike: int = 0,
    ce_hedge_anchor: float = 0.0,
    ce_sl_pct: float = 25.0,
    ce_reentry_enabled: int = 1,
    # Put wing
    pe_sell_strike: int = 0,
    pe_sell_anchor: float = 0.0,
    pe_hedge_strike: int = 0,
    pe_hedge_anchor: float = 0.0,
    pe_sl_pct: float = 25.0,
    pe_reentry_enabled: int = 1,
    execute_live: bool = True,
    current_spot: Optional[float] = None,
) -> dict:
    """
    V5.0 'Old & Gold' Architecture: Unified Single-Window Console Deployment ('Ek Hi Jagah Saari Chijen').
    1. Creates or finds the Unit Master Block (M1/M2/M3).
    2. Attaches Call Wing (CE Sell + CE Hedge) with status PENDING and trade_state PENDING.
    3. Attaches Put Wing (PE Sell + PE Hedge) with status PENDING and trade_state PENDING.
    4. Evaluates live Spot vs master_anchor_price:
       - If Spot >= Master Anchor (Bullish):
           * Executes PUT Wing LIVE (Hedge First -> then Sell PE) -> trade_state = 'OPEN'.
           * Leaves CALL Wing in PENDING (Armed on broker sidelines) -> trade_state = 'PENDING'.
       - If Spot < Master Anchor (Bearish):
           * Executes CALL Wing LIVE (Hedge First -> then Sell CE) -> trade_state = 'OPEN'.
           * Leaves PUT Wing in PENDING (Armed on broker sidelines) -> trade_state = 'PENDING'.
    """
    expiry_date = expiry_date.strip()
    unit_name = str(anchor_unit_name).strip().upper() if anchor_unit_name else "M1"

    # Step 1: Create or reuse Master Block
    res_block = create_block(
        expiry_date=expiry_date,
        expiry_type="MONTHLY",
        side_type="BOTH",
        notes=notes or f"Unified V5 Master Unit {unit_name}",
        anchor_unit_name=unit_name,
        master_anchor_price=float(master_anchor_price),
        regime_buffer=float(regime_buffer),
        custom_lots=int(recommended_lots),
        recommended_lots=int(recommended_lots),
        anchor_decision_time="15:00",
        orphan_hedge_policy="PRESERVE"
    )

    if not res_block.get("ok"):
        return {"ok": False, "message": f"Failed to create Master Block: {res_block.get('message')}"}

    block_id = res_block["block_id"]
    block_num = res_block["block_number"]

    ce_h_id = None
    ce_s_id = None
    pe_h_id = None
    pe_s_id = None

    # Step 2: Attach Call Wing (if configured)
    ce_sl_price = float(ce_sell_anchor) * (1.0 + (float(ce_sl_pct) / 100.0)) if float(ce_sell_anchor) > 0 else 0.0
    if ce_hedge_strike > 0:
        ce_h_id = db.add_strike(
            block_id=block_id,
            strike_price=int(ce_hedge_strike),
            option_type="CE",
            leg_type="HEDGE_BUY",
            anchor_price=float(ce_hedge_anchor),
            lots=int(recommended_lots),
            expiry_date=expiry_date,
            trade_state="PENDING"
        )
    if ce_sell_strike > 0:
        ce_s_id = db.add_strike(
            block_id=block_id,
            strike_price=int(ce_sell_strike),
            option_type="CE",
            leg_type="SELL",
            anchor_price=float(ce_sell_anchor),
            lots=int(recommended_lots),
            hedge_strike_id=ce_h_id,
            expiry_date=expiry_date,
            sl_pct=float(ce_sl_pct),
            sl_price=float(ce_sl_price),
            reentry_enabled=int(ce_reentry_enabled),
            trade_state="PENDING"
        )
        if ce_h_id and ce_s_id > 0:
            link_hedge_to_sell(ce_s_id, ce_h_id)

    # Step 3: Attach Put Wing (if configured)
    pe_sl_price = float(pe_sell_anchor) * (1.0 + (float(pe_sl_pct) / 100.0)) if float(pe_sell_anchor) > 0 else 0.0
    if pe_hedge_strike > 0:
        pe_h_id = db.add_strike(
            block_id=block_id,
            strike_price=int(pe_hedge_strike),
            option_type="PE",
            leg_type="HEDGE_BUY",
            anchor_price=float(pe_hedge_anchor),
            lots=int(recommended_lots),
            expiry_date=expiry_date,
            trade_state="PENDING"
        )
    if pe_sell_strike > 0:
        pe_s_id = db.add_strike(
            block_id=block_id,
            strike_price=int(pe_sell_strike),
            option_type="PE",
            leg_type="SELL",
            anchor_price=float(pe_sell_anchor),
            lots=int(recommended_lots),
            hedge_strike_id=pe_h_id,
            expiry_date=expiry_date,
            sl_pct=float(pe_sl_pct),
            sl_price=float(pe_sl_price),
            reentry_enabled=int(pe_reentry_enabled),
            trade_state="PENDING"
        )
        if pe_h_id and pe_s_id > 0:
            link_hedge_to_sell(pe_s_id, pe_h_id)

    # Step 4: Selective Execution based on Live Spot vs Master Anchor
    executed_side = "NONE"
    pending_side = "NONE"
    exec_details = {}

    spot = current_spot if (current_spot is not None and current_spot > 0) else kite_executor.get_nifty_spot()
    if spot <= 0 and master_anchor_price > 0:
        spot = master_anchor_price

    if execute_live and master_anchor_price > 0:
        if spot >= master_anchor_price:
            # 🟢 Bullish -> Execute PUT Wing LIVE; CALL Wing stays in PENDING
            executed_side = "PUT"
            pending_side = "CALL"
            db.update_block_regime(block_id, "BULLISH")
            if pe_s_id and pe_s_id > 0:
                exec_res = execute_strike(pe_s_id)
                exec_details["put_exec"] = exec_res
                if exec_res.get("ok"):
                    db.update_strike_trade_state(pe_s_id, "OPEN")
                    if pe_h_id:
                        db.update_strike_trade_state(pe_h_id, "OPEN")
            _log(f"🚀 V5 Master Unit {unit_name} Deployed: BULLISH (Spot ₹{spot:.2f} >= Anchor ₹{master_anchor_price:.2f}). Put Wing executed LIVE; Call Wing held in PENDING.", "OK")
        else:
            # 🔴 Bearish -> Execute CALL Wing LIVE; PUT Wing stays in PENDING
            executed_side = "CALL"
            pending_side = "PUT"
            db.update_block_regime(block_id, "BEARISH")
            if ce_s_id and ce_s_id > 0:
                exec_res = execute_strike(ce_s_id)
                exec_details["call_exec"] = exec_res
                if exec_res.get("ok"):
                    db.update_strike_trade_state(ce_s_id, "OPEN")
                    if ce_h_id:
                        db.update_strike_trade_state(ce_h_id, "OPEN")
            _log(f"🚀 V5 Master Unit {unit_name} Deployed: BEARISH (Spot ₹{spot:.2f} < Anchor ₹{master_anchor_price:.2f}). Call Wing executed LIVE; Put Wing held in PENDING.", "OK")

    tg.send(
        f"🚀 <b>V5 UNIFIED MASTER UNIT DEPLOYED</b> 🚀\n"
        f"Unit: <b>{unit_name}</b> (Block #{block_num})\n"
        f"Expiry: <b>{expiry_date}</b> | Lots: <b>{recommended_lots}</b>\n"
        f"Master Anchor: ₹<b>{master_anchor_price:,.2f}</b> | Spot: ₹<b>{spot:,.2f}</b>\n"
        f"⚡ <b>Executed Live:</b> {executed_side} Wing\n"
        f"🛡️ <b>Held in PENDING:</b> {pending_side} Wing\n"
        f"<i>Architecture: V5.0 'Old & Gold'</i>"
    )

    return {
        "ok": True,
        "block_id": block_id,
        "block_number": block_num,
        "unit_name": unit_name,
        "executed_side": executed_side,
        "pending_side": pending_side,
        "ce_sell_id": ce_s_id,
        "ce_hedge_id": ce_h_id,
        "pe_sell_id": pe_s_id,
        "pe_hedge_id": pe_h_id,
        "exec_details": exec_details,
        "message": f"Successfully deployed Unit {unit_name} (Block #{block_num}): {executed_side} Wing executed LIVE, {pending_side} Wing held in PENDING."
    }


def exit_orphan_hedge(hedge_strike_id: int) -> dict:
    """
    V5.0 Manual Profit Lock: 1-Click closure of an active Orphan Hedge.
    """
    strike = db.get_strike(hedge_strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {hedge_strike_id} not found."}
    if strike["leg_type"] != "HEDGE_BUY":
        return {"ok": False, "message": f"Strike {hedge_strike_id} is not a HEDGE_BUY leg."}
    if strike["status"] != "OPEN":
        return {"ok": False, "message": f"Hedge {hedge_strike_id} is not OPEN (status={strike['status']})."}

    # Execute market sell to exit long hedge
    sym_info = _resolve_symbol(strike)
    if not sym_info:
        return {"ok": False, "message": f"Could not resolve symbol for hedge {hedge_strike_id}."}

    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    qty = strike["lots"] * lot_size

    order_id, filled = kite_executor.execute_sell_and_confirm(
        trading_symbol=sym_info["trading_symbol"],
        symbol_token=sym_info["token"],
        qty=qty
    )

    if not filled or not order_id:
        return {"ok": False, "message": "Failed to close hedge order on broker."}

    fill_price = kite_executor.get_order_fill_price(order_id)
    if fill_price <= 0:
        fill_price = kite_executor.get_ltp(sym_info["token"], sym_info["trading_symbol"])
    if fill_price <= 0:
        fill_price = strike.get("anchor_price", 0.0)

    open_leg = db.get_open_leg(strike["strike_id"])
    leg_id = open_leg["leg_id"] if open_leg else None
    realized_pnl = 0.0
    if open_leg:
        realized_pnl = (fill_price - open_leg["entry_price"]) * qty
        db.close_leg(leg_id, fill_price, realized_pnl)
    db.update_strike_status(strike["strike_id"], "CLOSED")
    db.update_strike_trade_state(strike["strike_id"], "CLOSED")
    db.log_trade(
        block_id     = strike["block_id"],
        strike_id    = strike["strike_id"],
        action       = "CLOSE_HEDGE_PROFIT_LOCK",
        price        = fill_price,
        lots         = strike["lots"],
        order_status = "SUCCESS"
    )

    _log(f"💰 V5 Manual Profit Lock: Closed Orphan Hedge #{hedge_strike_id} ({strike['strike_price']} {strike['option_type']}) at ₹{fill_price:.2f}", "OK")
    return {"ok": True, "fill_price": fill_price, "realized_pnl": realized_pnl, "message": f"Successfully locked profit on Hedge {strike['strike_price']} {strike['option_type']} at ₹{fill_price:.2f}."}


def rearm_block_strikes(block_id: int) -> dict:
    """
    Re-arms all CLOSED strikes in a block back to PENDING.
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}
    
    strikes = db.get_strikes_by_block(block_id, status_filter="CLOSED")
    rearmed_count = 0
    for s in strikes:
        db.update_strike_status(s["strike_id"], "PENDING")
        rearmed_count += 1
    
    _log(f"Re-armed {rearmed_count} closed strike(s) in Block #{block['block_number']} [Unit {block.get('anchor_unit_name', 'M1')}] back to PENDING.", "OK")
    return {"ok": True, "rearmed_count": rearmed_count, "message": f"Re-armed {rearmed_count} strike(s) in Block #{block['block_number']}."}


def kill_block(block_id: int) -> dict:
    """
    Emergency Kill Unit: Market-closes all open SELL and HEDGE legs strictly for this block.
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}

    open_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN")
    closed_count = 0
    errs = []
    
    # 1. Close Sell Legs first
    for s in open_strikes:
        if s["leg_type"] == "SELL":
            res = close_strike(s["strike_id"], close_hedge=True)
            if res.get("ok"):
                closed_count += 1
            else:
                errs.append(f"Strike {s['strike_price']} {s['option_type']}: {res.get('message')}")

    # 2. Close any remaining open Hedges
    remaining_open = db.get_strikes_by_block(block_id, status_filter="OPEN")
    for s in remaining_open:
        res = close_strike(s["strike_id"], close_hedge=False)
        if res.get("ok"):
            closed_count += 1
        else:
            errs.append(f"Hedge {s['strike_price']} {s['option_type']}: {res.get('message')}")

    _log(f"Emergency Kill Unit for Block #{block['block_number']} [Unit {block.get('anchor_unit_name', 'M1')}]: {closed_count} strikes closed.", "ALERT")
    if errs:
        return {"ok": False, "closed_count": closed_count, "message": f"Closed {closed_count} legs with errors: " + "; ".join(errs)}
    return {"ok": True, "closed_count": closed_count, "message": f"Successfully killed Unit {block.get('anchor_unit_name', 'M1')} (Block #{block['block_number']}). {closed_count} legs closed."}


def toggle_block_enabled(block_id: int, is_enabled: bool) -> dict:
    """
    Toggles ENABLED / PAUSED status for a block.
    """
    ok = db.toggle_block_enabled(block_id, is_enabled)
    status_str = "ENABLED" if is_enabled else "PAUSED"
    if ok:
        _log(f"Block {block_id} toggle -> {status_str}", "OK")
        b = db.get_block(block_id)
        if b:
            tg.alert_block_toggled(b["block_number"], b.get("side_type", "BOTH"), is_enabled)
        return {"ok": True, "message": f"Block {block_id} set to {status_str}."}
    return {"ok": False, "message": f"Failed to update status for Block {block_id}."}


def get_block_summary(block_id: int) -> dict:
    """
    Returns full summary for a block — used by dashboard.
    Includes: block info + all strikes + open legs + P&L (if ltp_map provided).

    Returns:
    {
      "block": {...},
      "strikes": [
        {
          "strike_id", "strike_price", "option_type", "leg_type",
          "anchor_price", "lots", "status", "hedge_strike_id",
          "open_leg": {...} or None,
          "hedge_partner": {...} or None   <- linked hedge/sell strike
        }
      ],
      "total_strikes": int,
      "open_strikes": int,
    }
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}

    strikes     = db.get_strikes_by_block(block_id)
    enriched    = []
    open_count  = 0

    for s in strikes:
        open_leg = db.get_open_leg(s["strike_id"])
        if s["status"] in ("OPEN", "PENDING_CLOSE"):
            open_count += 1

        # Find hedge partner
        hedge_partner = None
        if s.get("hedge_strike_id"):
            hedge_partner = db.get_strike(s["hedge_strike_id"])

        enriched.append({
            **s,
            "open_leg":     open_leg or None,
            "hedge_partner": hedge_partner or None,
        })

    return {
        "ok":           True,
        "block":        block,
        "strikes":      enriched,
        "total_strikes": len(strikes),
        "open_strikes": open_count,
    }


def get_all_blocks_summary() -> list:
    """
    Returns summary for ALL blocks (used by dashboard main view).
    """
    blocks  = db.get_all_blocks()
    results = []
    for b in blocks:
        s = get_block_summary(b["block_id"])
        results.append(s)
    return results


def archive_block(block_id: int) -> dict:
    """
    Manually archive (CLOSE) a block.
    HARD RULE: Cannot close if any strike is OPEN.
    """
    ok = db.update_block_status(block_id, "CLOSED")
    if ok:
        return {"ok": True, "message": f"Block {block_id} archived (CLOSED)."}
    return {"ok": False, "message": f"Cannot archive block {block_id} -- open strikes exist."}


def delete_block(block_id: int) -> dict:
    """
    Deletes a block and all its strikes/legs.
    HARD RULE: Cannot delete if any strike is OPEN.
    """
    ok = db.delete_block(block_id)
    if ok:
        return {"ok": True, "message": f"Block {block_id} deleted."}
    return {"ok": False, "message": f"Cannot delete block {block_id} -- open strikes exist."}


# ─────────────────────────────────────────────────────────────────────────────
# STRIKE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_strike_to_block(
    block_id:     int,
    strike_price: int,
    option_type:  str,
    leg_type:     str,
    anchor_price: float,
    lots:         int = 1,
    expiry_date:  str = None,
    sl_pct:       float = 25.0,
    sl_price:     float = 0.0,
    reentry_enabled: int = 1,
    trade_state:  str = "PENDING",
) -> dict:
    """
    Adds a strike (sell leg or hedge leg) to a block.
    Does NOT place order yet -- just stores in DB.

    HARD RULES checked (via db.add_strike):
      - Max strikes per block (configurable)
      - CE / PE only
      - SELL / HEDGE_BUY only
      - Anchor price > 0 (manual entry required)
      - V5 Invariant: SL is auto-computed as Anchor + 25% if not provided

    Returns: {"ok": bool, "strike_id": int, "message": str}
    """
    # Verify block is still ACTIVE
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}
    if block["status"] != "ACTIVE":
        return {"ok": False, "message": f"Block {block_id} is {block['status']} -- cannot add strikes."}

    # Strict Call / Put Side Type validation
    b_side = (block.get("side_type") or "BOTH").strip().upper()
    opt_upper = option_type.strip().upper()
    if b_side == "CALL" and opt_upper != "CE":
        return {"ok": False, "message": f"Block #{block['block_number']} is a CALL SIDE block. Only CE strikes are allowed."}
    if b_side == "PUT" and opt_upper != "PE":
        return {"ok": False, "message": f"Block #{block['block_number']} is a PUT SIDE block. Only PE strikes are allowed."}

    strike_id = db.add_strike(
        block_id        = block_id,
        strike_price    = strike_price,
        option_type     = option_type,
        leg_type        = leg_type,
        anchor_price    = anchor_price,
        lots            = lots,
        expiry_date     = expiry_date,
        sl_pct          = float(sl_pct),
        sl_price        = float(sl_price),
        reentry_enabled = int(reentry_enabled),
        trade_state     = str(trade_state).upper(),
    )

    if strike_id < 0:
        max_str = db.get("max_strikes_per_block", "50")
        return {
            "ok":      False,
            "message": (
                f"Cannot add strike {strike_price} {option_type} {leg_type}. "
                f"Check: max {max_str} strikes, anchor > 0, valid CE/PE, valid SELL/HEDGE_BUY."
            ),
        }

    qty = lots * int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    _log(
        f"Strike added: Block {block_id} | {strike_price} {option_type} {leg_type} "
        f"| Anchor=Rs{anchor_price:.2f} | Lots={lots} | Qty={qty} | Expiry={expiry_date}",
        "OK"
    )
    return {
        "ok":        True,
        "strike_id": strike_id,
        "qty":       qty,
        "message":   f"Strike {strike_price} {option_type} {leg_type} added to Block {block['block_number']}.",
    }


def link_hedge_to_sell(sell_strike_id: int, hedge_strike_id: int) -> dict:
    """
    Links a HEDGE_BUY strike to its paired SELL strike with strict spread geometry validation.
    Both strikes must be in the same block.

    HARD RULES enforced:
      1. Both strikes must be the same option_type (CE-CE, PE-PE).
      2. For CE: hedge_strike_price > sell_strike_price (OTM higher strike).
      3. For PE: hedge_strike_price < sell_strike_price (OTM lower strike).

    Returns: {"ok": bool, "message": str}
    """
    sell   = db.get_strike(sell_strike_id)
    hedge  = db.get_strike(hedge_strike_id)

    if not sell:
        return {"ok": False, "message": f"Sell strike {sell_strike_id} not found."}
    if not hedge:
        return {"ok": False, "message": f"Hedge strike {hedge_strike_id} not found."}

    if sell["block_id"] != hedge["block_id"]:
        return {"ok": False, "message": "Sell and hedge strikes must be in the same block."}

    if sell["leg_type"] != "SELL":
        return {"ok": False, "message": f"Strike {sell_strike_id} is not a SELL leg."}

    if hedge["leg_type"] != "HEDGE_BUY":
        return {"ok": False, "message": f"Strike {hedge_strike_id} is not a HEDGE_BUY leg."}

    sell_opt = sell["option_type"].strip().upper()
    hedge_opt = hedge["option_type"].strip().upper()
    if sell_opt != hedge_opt:
        return {"ok": False, "message": f"Option type mismatch: Sell is {sell_opt} but Hedge is {hedge_opt}."}

    sell_sp = int(sell["strike_price"])
    hedge_sp = int(hedge["strike_price"])

    # ── Strict Mathematical Spread Guardrails ──
    if sell_opt == "CE" and hedge_sp <= sell_sp:
        msg = f"Invalid CE Spread Geometry: Hedge strike ({hedge_sp} CE) must be strictly HIGHER than Sell strike ({sell_sp} CE) for Option Selling."
        _log(f"REJECTED LINK: {msg}", "ERROR")
        return {"ok": False, "message": msg}

    if sell_opt == "PE" and hedge_sp >= sell_sp:
        msg = f"Invalid PE Spread Geometry: Hedge strike ({hedge_sp} PE) must be strictly LOWER than Sell strike ({sell_sp} PE) for Option Selling."
        _log(f"REJECTED LINK: {msg}", "ERROR")
        return {"ok": False, "message": msg}

    ok = db.link_hedge(sell_strike_id, hedge_strike_id)
    if ok:
        _log(f"Hedge linked: Sell {sell_strike_id} ({sell['strike_price']} {sell['option_type']}) <-> Hedge {hedge_strike_id} ({hedge['strike_price']} {hedge['option_type']})", "OK")
        return {"ok": True, "message": f"Hedge linked: Strike {sell_strike_id} <-> Hedge {hedge_strike_id}."}

    return {"ok": False, "message": "DB error linking hedge."}


def remove_strike(strike_id: int) -> dict:
    """
    Removes a PENDING (not yet executed) strike from a block.
    Cannot remove OPEN strikes (live positions).

    Returns: {"ok": bool, "message": str}
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}

    if strike["status"] == "OPEN":
        return {"ok": False, "message": f"Cannot remove OPEN strike {strike_id} -- has live position."}

    ok = db.delete_strike(strike_id)
    if ok:
        return {"ok": True, "message": f"Strike {strike_id} removed."}
    return {"ok": False, "message": f"DB error removing strike {strike_id}."}


def change_strike_lots(strike_id: int, new_lots: int, sync_live: bool = False) -> dict:
    """
    Updates lot count for a strike.
    If sync_live is True and strike is OPEN, places incremental orders on Zerodha
    to scale up or scale down live positions to match new_lots.
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}

    if new_lots < 1:
        return {"ok": False, "message": "Lots must be >= 1."}

    old_lots = strike["lots"]
    status = strike["status"]

    ok = db.update_strike_lots(strike_id, new_lots)
    if not ok:
        return {"ok": False, "message": "DB error updating strike lots."}

    # Also update paired hedge if present
    if strike.get("hedge_strike_id"):
        db.update_strike_lots(strike["hedge_strike_id"], new_lots)

    msg = f"Strike {strike_id} lots updated: {old_lots} -> {new_lots}."

    # Live sync for OPEN positions if requested
    if sync_live and status == "OPEN" and new_lots != old_lots:
        delta_lots = new_lots - old_lots
        lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
        delta_qty = abs(delta_lots) * lot_size

        sym_info = _resolve_symbol(strike)
        if not sym_info:
            return {"ok": True, "message": f"{msg} (Warning: Symbol resolution failed for live sync)."}

        tsymbol = sym_info["trading_symbol"]
        token   = sym_info["token"]

        if delta_lots > 0:
            tx_type = "SELL" if strike["leg_type"] == "SELL" else "BUY"
            _log(f"Live Sync: Scaling UP Strike {strike_id} +{delta_lots} lots ({delta_qty} qty) -> {tx_type} {tsymbol}")
            order_id = kite_executor.place_order(tx_type, token, delta_qty, tsymbol, "MARKET")
            if order_id:
                db.record_trade(strike["block_id"], strike_id, f"SCALE_UP_{tx_type}", 0.0, delta_lots, "COMPLETE")
                msg += f" Executed Live Order: {order_id} ({tx_type} {delta_qty} qty)."
            else:
                msg += " Live Sync order failed on broker."
        else:
            tx_type = "BUY" if strike["leg_type"] == "SELL" else "SELL"
            _log(f"Live Sync: Scaling DOWN Strike {strike_id} -{abs(delta_lots)} lots ({delta_qty} qty) -> {tx_type} {tsymbol}")
            order_id = kite_executor.place_order(tx_type, token, delta_qty, tsymbol, "MARKET")
            if order_id:
                db.record_trade(strike["block_id"], strike_id, f"SCALE_DOWN_{tx_type}", 0.0, abs(delta_lots), "COMPLETE")
                msg += f" Executed Live Order: {order_id} ({tx_type} {delta_qty} qty)."
            else:
                msg += " Live Sync order failed on broker."

    b = db.get_block(strike["block_id"])
    b_num = b.get("block_number", 0) if b else 0
    tg.alert_strike_lots_updated(b_num, strike["strike_price"], strike["option_type"], old_lots, new_lots, msg)

    _log(msg, "OK")
    return {"ok": True, "message": msg}


def update_strike_anchor_price(strike_id: int, new_anchor: float) -> dict:
    """
    Updates the anchor price of a strike.
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}
    if new_anchor <= 0:
        return {"ok": False, "message": "Anchor price must be > 0."}
    
    old_anc = float(strike.get("anchor_price") or 0.0)
    ok = db.update_strike_anchor_price(strike_id, new_anchor)
    if ok:
        _log(f"Strike {strike_id} ({strike['strike_price']} {strike['option_type']}) anchor price updated: ₹{old_anc:.2f} -> ₹{new_anchor:.2f}", "OK")
        return {"ok": True, "message": f"Strike {strike['strike_price']} {strike['option_type']} anchor price updated to ₹{new_anchor:.2f}."}
    return {"ok": False, "message": f"Database error updating anchor price for strike {strike_id}."}


def scale_block_lots(block_id: int, new_lots: int, sync_live: bool = False) -> dict:
    """
    Scales all strikes in a block to new_lots.
    """
    strikes = db.get_strikes_by_block(block_id)
    if not strikes:
        return {"ok": False, "message": "No strikes in this block."}
    updated_count = 0
    for s in strikes:
        res = change_strike_lots(s["strike_id"], new_lots, sync_live=sync_live)
        if res["ok"]:
            updated_count += 1
    return {"ok": True, "message": f"Updated lot size to {new_lots} across {updated_count} strike(s) in Block."}


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION — EXECUTE SINGLE STRIKE
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_symbol(strike: dict) -> Optional[dict]:
    """
    Resolves option symbol + token via Kite executor.
    Returns: {"token": str, "trading_symbol": str} or None
    """
    block = db.get_block(strike["block_id"])
    if not block:
        return None

    expiry = strike.get("expiry_date")
    if not expiry:
        expiry = block["expiry_date"]

    return kite_executor.search_option_symbol(
        expiry_date  = expiry,
        strike_price = int(strike["strike_price"]),
        option_type  = strike["option_type"],
    )


def execute_strike(strike_id: int) -> dict:
    """
    Executes a single strike (places the order).

    For SELL strikes: also executes its linked HEDGE_BUY first.
    HARD RULE: Entry sequence = BUY hedge FIRST -> confirm -> SELL option.

    For HEDGE_BUY strikes: executed standalone (if no paired sell yet).

    Returns:
    {
      "ok": bool,
      "sell_order_id": str or None,
      "hedge_order_id": str or None,
      "fill_price": float,
      "message": str,
    }
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}

    block = db.get_block(strike["block_id"])
    if not block:
        return {"ok": False, "message": "Block not found."}

    # ── STRICT REGIME GOVERNOR CHECK (V3.0 Multi-Anchor Guardrail) ──
    # If this strike's option_type is MUTED by the regime (e.g. CE in Bullish, PE in Bearish),
    # REJECT manual and automated execution. Strike must remain PENDING (Armed for regime flip).
    import regime_engine as re_eng
    is_allowed, regime_reason = re_eng.is_strike_allowed_by_regime(strike["option_type"], block=block)
    if not is_allowed:
        unit_name = block.get("anchor_unit_name") or f"M{block['block_number']}"
        regime_name = block.get("current_regime") or "UNKNOWN"
        msg = f"Execution blocked: Strike {strike['strike_price']} {strike['option_type']} is MUTED under Unit {unit_name} {regime_name} regime ({regime_reason}). Strike remains in PENDING (Armed)."
        _log(f"[REGIME-GUARD-BLOCKED] {msg}", "WARN")
        return {
            "ok": False,
            "blocked_by_regime": True,
            "message": msg,
        }

    # Whitelist / execution check: Prevent entry if already breached (LTP >= anchor + buffer)
    if strike["leg_type"] == "SELL":
        symbol_info = _resolve_symbol(strike)
        if symbol_info:
            current_ltp = kite_executor.get_ltp(symbol_info["token"], symbol_info["trading_symbol"])
            if current_ltp <= 0:
                current_ltp = kite_executor.get_live_ltp(symbol_info["token"], symbol_info["trading_symbol"])
            
            if current_ltp > 0:
                anchor_price = float(strike["anchor_price"])
                buffer_tolerance = float(db.get("buffer_tolerance", "2.0"))
                exit_threshold = anchor_price + buffer_tolerance
                if current_ltp >= exit_threshold:
                    _log(f"Execution blocked: Current LTP (Rs {current_ltp:.2f}) is above the exit threshold (Rs {exit_threshold:.2f}) for strike {strike_id}.", "WARN")
                    return {
                        "ok": False,
                        "message": f"Execution blocked: Current LTP (Rs {current_ltp:.2f}) is above the exit threshold (Rs {exit_threshold:.2f}). Please update your anchor price first.",
                    }

    if strike["status"] not in ("PENDING", "CLOSED"):
        return {"ok": False, "message": f"Strike {strike_id} status is {strike['status']} -- only PENDING or CLOSED strikes can be executed."}

    status_before = strike["status"]

    # Atomically lock the main strike by setting it to EXECUTING based on its current status
    if status_before == "PENDING":
        locked = db.try_set_strike_executing(strike_id)
    else:
        locked = db.try_set_strike_reentering(strike_id)

    if not locked:
        return {"ok": False, "message": f"Strike {strike_id} is already executing or status changed."}

    lot_size    = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    qty         = strike["lots"] * lot_size

    _log(f"Executing strike {strike_id}: {strike['strike_price']} {strike['option_type']} {strike['leg_type']} | Qty={qty}", "ORDER")


    # ── Case 1: SELL leg → execute hedge first, then sell ────────────────────
    if strike["leg_type"] == "SELL":

        # Check if linked hedge exists
        hedge_strike_id = strike.get("hedge_strike_id")
        hedge_strike    = db.get_strike(hedge_strike_id) if hedge_strike_id else None

        # ── Feature B: Entry Guard ──────────────────────────────────────────
        # If this sell has no hedge linked, scan block for any OPEN HEDGE_BUY
        # of the same option type that is not yet linked to any other sell.
        # This prevents buying a redundant hedge when one is already open.
        if not hedge_strike_id or not hedge_strike or hedge_strike["status"] not in ("OPEN", "PENDING"):
            block_strikes = db.get_strikes_by_block(strike["block_id"])
            unlinked_open_hedges = [
                h for h in block_strikes
                if h["leg_type"] == "HEDGE_BUY"
                and h["status"] == "OPEN"
                and h["option_type"] == strike["option_type"]  # same direction CE→CE, PE→PE
                and (h.get("hedge_strike_id") is None or h.get("hedge_strike_id") == strike_id)
            ]
            if unlinked_open_hedges:
                candidate = unlinked_open_hedges[0]
                _log(
                    f"[ENTRY-GUARD] Found existing open hedge {candidate['strike_id']} "
                    f"({candidate['strike_price']} {candidate['option_type']}) for sell {strike_id}. "
                    f"Auto-linking instead of buying new hedge.",
                    "INFO"
                )
                link_hedge_to_sell(strike_id, candidate["strike_id"])
                hedge_strike_id = candidate["strike_id"]
                hedge_strike    = db.get_strike(hedge_strike_id)
            elif hedge_strike and hedge_strike["status"] == "CLOSED":
                _log(
                    f"[SAFE-HEDGE] Linked hedge {hedge_strike_id} was CLOSED. "
                    f"Resetting to PENDING to buy fresh hedge first before selling.",
                    "INFO"
                )
                db.update_strike_status(hedge_strike_id, "PENDING")
                hedge_strike = db.get_strike(hedge_strike_id)

        # ── Step 0: Spread Geometry Validation (Prevents Debit Spread Disasters) ──
        if hedge_strike:
            s_opt = strike["option_type"].strip().upper()
            h_opt = hedge_strike["option_type"].strip().upper()
            s_sp  = int(strike["strike_price"])
            h_sp  = int(hedge_strike["strike_price"])

            if s_opt != h_opt:
                db.update_strike_status(strike_id, status_before)
                return {"ok": False, "message": f"Execution Aborted: Option type mismatch ({s_opt} vs {h_opt})."}

            if s_opt == "CE" and h_sp <= s_sp:
                db.update_strike_status(strike_id, status_before)
                err_msg = f"Execution Aborted: Inverted CE hedge ({h_sp} CE <= {s_sp} CE). Hedge strike must be strictly HIGHER for CE selling."
                _log(err_msg, "ERROR")
                return {"ok": False, "message": err_msg}

            if s_opt == "PE" and h_sp >= s_sp:
                db.update_strike_status(strike_id, status_before)
                err_msg = f"Execution Aborted: Inverted PE hedge ({h_sp} PE >= {s_sp} PE). Hedge strike must be strictly LOWER for PE selling."
                _log(err_msg, "ERROR")
                return {"ok": False, "message": err_msg}

        hedge_was_pending = False
        if hedge_strike and hedge_strike["status"] == "PENDING":
            # Atomically lock the hedge strike by setting it to EXECUTING
            hedge_was_pending = db.try_set_strike_executing(hedge_strike_id)

        # Step A: Execute hedge BUY first (HARD RULE from blueprint)
        if hedge_strike and (hedge_was_pending or hedge_strike["status"] == "OPEN"):
            if hedge_was_pending:
                _log(f"Entry sequence: BUY hedge FIRST (Strike {hedge_strike_id})", "ORDER")
                # Fetch updated hedge strike record with status='EXECUTING'
                updated_hedge_strike = db.get_strike(hedge_strike_id)
                hedge_result = _execute_buy_leg(updated_hedge_strike, qty)
                if not hedge_result["ok"]:
                    # Rollback both strikes to original status
                    db.update_strike_status(strike_id, status_before)
                    db.update_strike_status(hedge_strike_id, "PENDING")
                    return {
                        "ok": False,
                        "message": f"Hedge BUY failed for strike {hedge_strike_id}: {hedge_result['message']}. Aborting sell.",
                    }
                _log(f"Hedge BUY confirmed: {hedge_strike['strike_price']} {hedge_strike['option_type']} @ Rs{hedge_result['fill_price']:.2f}", "OK")
            elif hedge_strike["status"] == "OPEN":
                _log(f"Hedge {hedge_strike_id} already OPEN (auto-linked or pre-existing). Proceeding to sell.", "INFO")
        else:
            _log(f"WARNING: No hedge linked to sell strike {strike_id}. Proceeding without hedge (unhedged sell).", "WARN")

        # Step B: Place SELL order
        updated_strike = db.get_strike(strike_id)
        sell_result = _execute_sell_leg(updated_strike, qty)
        if not sell_result["ok"]:
            # Rollback sell strike to status_before
            db.update_strike_status(strike_id, status_before)
            
            # If we bought a fresh hedge in this cycle but the sell failed, immediately square off the hedge
            # to protect the user from being left with a naked bleeding long option!
            if hedge_was_pending and hedge_strike_id:
                _log(f"CRITICAL: SELL order failed after buying hedge {hedge_strike_id}. Executing emergency hedge square-off to avoid naked long exposure...", "ALERT")
                close_res = close_hedge_strike_now(hedge_strike_id)
                tg.send(
                    f"⚠️ <b>CRITICAL EXECUTION ERROR</b> ⚠️\n"
                    f"Block {block.get('block_number', '?')} | {strike['strike_price']} {strike['option_type']} SELL order failed!\n"
                    f"Error: {sell_result['message']}\n"
                    f"🛡️ Emergency hedge {hedge_strike['strike_price']} {hedge_strike['option_type']} square-off: {close_res.get('message', 'Triggered')}"
                )
            
            return {
                "ok":     False,
                "message": f"SELL order failed: {sell_result['message']}. Emergency hedge square-off attempted.",
            }

        _log(f"SELL confirmed: {strike['strike_price']} {strike['option_type']} @ Rs{sell_result['fill_price']:.2f}", "OK")

        # V5.0 Invariant: Anchor Stop-Loss Trigger to exact Fill Price + 25%
        fill_price = float(sell_result.get("fill_price", 0.0))
        if fill_price > 0:
            sl_pct = float(updated_strike.get("sl_pct") or 25.0)
            exact_sl_price = fill_price * (1.0 + (sl_pct / 100.0))
            db.update_strike_sl_config(strike_id, sl_pct=sl_pct, sl_price=exact_sl_price)
            _log(f"[V5-SL-ANCHOR] Strike {strike['strike_price']} {strike['option_type']} SELL: Fill=₹{fill_price:.2f} -> SL Price set to ₹{exact_sl_price:.2f} (+{sl_pct:.0f}%)", "OK")

        # Log to trade history
        db.log_trade(
            block_id     = strike["block_id"],
            strike_id    = strike_id,
            action       = "ENTRY",
            price        = sell_result["fill_price"],
            lots         = strike["lots"],
            order_status = "SUCCESS",
        )

        return {
            "ok":            True,
            "sell_order_id": sell_result["order_id"],
            "hedge_order_id": hedge_strike_id,
            "fill_price":    sell_result["fill_price"],
            "message":       f"Strike {strike['strike_price']} {strike['option_type']} SELL executed @ Rs{sell_result['fill_price']:.2f}.",
        }

    # ── Case 2: HEDGE_BUY standalone ─────────────────────────────────────────
    elif strike["leg_type"] == "HEDGE_BUY":
        updated_strike = db.get_strike(strike_id)
        result = _execute_buy_leg(updated_strike, qty)
        if result["ok"]:
            db.log_trade(
                block_id     = strike["block_id"],
                strike_id    = strike_id,
                action       = "HEDGE_ENTRY",
                price        = result["fill_price"],
                lots         = strike["lots"],
                order_status = "SUCCESS",
            )
        else:
            # Rollback standalone hedge to status_before
            db.update_strike_status(strike_id, status_before)
        return result

    return {"ok": False, "message": f"Unknown leg_type: {strike['leg_type']}"}


def _find_existing_broker_order(token: str, trading_symbol: str, transaction_type: str, qty: int) -> Optional[str]:
    """
    Reconciliation Guard: Checks if a matching trade already exists on the broker today.
    Returns: order_id if found, else None.
    """
    try:
        orders = kite_executor.get_all_orders()
        for o in orders:
            ord_token = str(o.get("security_id") or o.get("symboltoken") or o.get("tradingsymbol") or "")
            ord_symbol = str(o.get("tradingsymbol") or "")
            ord_type = str(o.get("transaction_type") or "").upper()
            ord_qty = int(o.get("quantity") or 0)
            ord_status = str(o.get("status") or "").upper()

            target_type = transaction_type.upper()
            if target_type == "HEDGE_BUY":
                target_type = "BUY"

            if ord_type != target_type:
                continue
            if ord_qty != qty:
                continue

            token_match = (ord_token == str(token) or ord_token == str(trading_symbol))
            symbol_match = (ord_symbol == str(trading_symbol) or ord_symbol == str(token))

            if token_match or symbol_match:
                if ord_status not in ("REJECTED", "CANCELLED", "DECLINED", "FAILED"):
                    order_id = str(o.get("order_id") or o.get("orderid") or "")
                    if order_id:
                        conn = db._conn()
                        linked = conn.execute("SELECT 1 FROM legs WHERE order_id = ?", (order_id,)).fetchone()
                        conn.close()
                        if not linked:
                            return order_id
    except Exception as e:
        _log(f"Exception in _find_existing_broker_order: {e}", "WARN")
    return None


def reconcile_active_blocks() -> int:
    """
    Scans all ACTIVE blocks with PENDING strikes and matches them with
    today's broker order book. If a match is found, links the order,
    creates the leg, and updates the strike status to OPEN.
    Returns: count of strikes successfully reconciled.
    """
    reconciled_count = 0
    try:
        blocks = db.get_all_blocks(status_filter="ACTIVE")
        for b in blocks:
            strikes = db.get_strikes_by_block(b["block_id"], status_filter="PENDING")
            for s in strikes:
                symbol_info = _resolve_symbol(s)
                if not symbol_info:
                    continue

                qty = s["lots"] * int(db.get("lot_size", "65"))
                order_id = _find_existing_broker_order(
                    token=symbol_info["token"],
                    trading_symbol=symbol_info["trading_symbol"],
                    transaction_type=s["leg_type"],
                    qty=qty
                )
                if order_id:
                    fill_price = kite_executor.get_order_fill_price(order_id)
                    if fill_price <= 0:
                        fill_price = kite_executor.get_ltp(symbol_info["token"], symbol_info["trading_symbol"])
                    if fill_price <= 0:
                        fill_price = s["anchor_price"]

                    db.create_leg(s["strike_id"], fill_price, order_id)
                    _log(f"[RECONCILE] Automatically reconciled Strike {s['strike_id']} with broker Order ID {order_id} at price {fill_price}.", "OK")
                    reconciled_count += 1
    except Exception as e:
        _log(f"Exception in reconcile_active_blocks: {e}", "ERROR")
    return reconciled_count


def _execute_sell_leg(strike: dict, qty: int) -> dict:
    """Internal: resolves symbol and places SELL order."""
    symbol_info = _resolve_symbol(strike)
    if not symbol_info:
        return {"ok": False, "message": f"Could not resolve symbol for {strike['strike_price']} {strike['option_type']}."}

    # Reconciliation Guard: Check if matching order exists on broker first
    order_id = _find_existing_broker_order(
        token=symbol_info["token"],
        trading_symbol=symbol_info["trading_symbol"],
        transaction_type="SELL",
        qty=qty
    )
    if order_id:
        _log(f"Reconciliation: Order {order_id} already exists on broker. Reusing it.", "INFO")
        filled = True
    else:
        order_id, filled = kite_executor.execute_sell_and_confirm(
            trading_symbol = symbol_info["trading_symbol"],
            symbol_token   = symbol_info["token"],
            qty            = qty,
        )

    if not filled or not order_id:
        db.update_strike_status(strike["strike_id"], "PENDING")
        return {"ok": False, "order_id": order_id, "message": "SELL order did not fill."}

    # Record leg fill using actual execution price
    fill_price = kite_executor.get_order_fill_price(order_id)
    if fill_price <= 0:
        fill_price = kite_executor.get_ltp(symbol_info["token"], symbol_info["trading_symbol"])
    if fill_price <= 0:
        fill_price = strike["anchor_price"]
    db.create_leg(strike["strike_id"], fill_price, order_id)

    return {"ok": True, "order_id": order_id, "fill_price": fill_price}


def _execute_buy_leg(strike: dict, qty: int) -> dict:
    """Internal: resolves symbol and places BUY order."""
    symbol_info = _resolve_symbol(strike)
    if not symbol_info:
        return {"ok": False, "message": f"Could not resolve symbol for {strike['strike_price']} {strike['option_type']}."}

    # Reconciliation Guard: Check if matching order exists on broker first
    order_id = _find_existing_broker_order(
        token=symbol_info["token"],
        trading_symbol=symbol_info["trading_symbol"],
        transaction_type="BUY",
        qty=qty
    )
    if order_id:
        _log(f"Reconciliation: Order {order_id} already exists on broker. Reusing it.", "INFO")
        filled = True
    else:
        order_id, filled = kite_executor.execute_buy_and_confirm(
            trading_symbol = symbol_info["trading_symbol"],
            symbol_token   = symbol_info["token"],
            qty            = qty,
        )

    if not filled or not order_id:
        db.update_strike_status(strike["strike_id"], "PENDING")
        return {"ok": False, "order_id": order_id, "message": "BUY order did not fill."}

    fill_price = kite_executor.get_order_fill_price(order_id)
    if fill_price <= 0:
        fill_price = kite_executor.get_ltp(symbol_info["token"], symbol_info["trading_symbol"])
    if fill_price <= 0:
        fill_price = strike["anchor_price"]
    db.create_leg(strike["strike_id"], fill_price, order_id)

    return {"ok": True, "order_id": order_id, "fill_price": fill_price}


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION — EXECUTE FULL BLOCK
# ─────────────────────────────────────────────────────────────────────────────

def execute_block(block_id: int) -> dict:
    """
    Executes pending strikes in a block, strictly filtered by Regime Governor.
    Order: Hedge strikes first, then Sell strikes.
    Muted strikes are safely skipped and retained in PENDING (Armed for regime flip).

    Returns:
    {
      "ok": bool,
      "executed": [strike_id, ...],
      "failed":   [strike_id, ...],
      "muted_pending": [strike_id, ...],
      "message":  str,
    }
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}

    if block["status"] != "ACTIVE":
        return {"ok": False, "message": f"Block {block_id} is {block['status']} -- cannot execute."}

    strikes  = db.get_strikes_by_block(block_id, status_filter="PENDING")
    if not strikes:
        return {"ok": False, "message": f"No PENDING strikes in Block {block_id}."}

    unit_name = block.get("anchor_unit_name") or f"M{block['block_number']}"
    _log(f"Executing Block {block['block_number']} [Unit {unit_name}] ({block['expiry_date']}) -- {len(strikes)} pending strikes...", "ORDER")

    executed = []
    failed   = []
    muted_pending = []

    import regime_engine as re_eng

    # Phase 1: Standalone HEDGE_BUY strikes (if any without linked sell)
    hedge_only = [s for s in strikes if s["leg_type"] == "HEDGE_BUY" and not s.get("hedge_strike_id")]
    for s in hedge_only:
        is_allowed, regime_reason = re_eng.is_strike_allowed_by_regime(s["option_type"], block=block)
        if not is_allowed:
            _log(f"[REGIME-GUARD] Standalone Hedge #{s['strike_id']} {s['strike_price']} {s['option_type']} is MUTED by regime. Retaining PENDING.", "WARN")
            muted_pending.append(s["strike_id"])
            continue
        result = execute_strike(s["strike_id"])
        if result["ok"]:
            executed.append(s["strike_id"])
        else:
            _log(f"Strike {s['strike_id']} failed: {result['message']}", "ERROR")
            failed.append(s["strike_id"])

    # Phase 2: Execute SELL strikes (each handles its own linked hedge internally)
    sell_strikes = [s for s in strikes if s["leg_type"] == "SELL"]
    for s in sell_strikes:
        is_allowed, regime_reason = re_eng.is_strike_allowed_by_regime(s["option_type"], block=block)
        if not is_allowed:
            _log(f"[REGIME-GUARD] SELL Strike #{s['strike_id']} {s['strike_price']} {s['option_type']} is MUTED under Unit {unit_name} {block.get('current_regime')} regime. Retaining PENDING (Armed).", "WARN")
            muted_pending.append(s["strike_id"])
            continue
        result = execute_strike(s["strike_id"])
        if result["ok"]:
            executed.append(s["strike_id"])
        elif result.get("blocked_by_regime"):
            muted_pending.append(s["strike_id"])
        else:
            _log(f"Strike {s['strike_id']} failed: {result['message']}", "ERROR")
            failed.append(s["strike_id"])

    total       = len(strikes)
    ok_count    = len(executed)
    fail_count  = len(failed)
    muted_count = len(muted_pending)

    if ok_count > 0:
        msg = f"Block {block['block_number']} [Unit {unit_name}]: {ok_count} active strike(s) executed."
        if muted_count > 0:
            msg += f" {muted_count} muted strike(s) retained in PENDING (Armed for regime shift)."
        is_ok = (fail_count == 0)
    elif muted_count > 0:
        msg = f"Block {block['block_number']} [Unit {unit_name}]: All {muted_count} pending strike(s) are MUTED under {block.get('current_regime')} regime. Retained armed in PENDING for regime shift."
        is_ok = True
    else:
        msg = f"Block {block['block_number']}: 0 strikes executed, {fail_count} failed."
        is_ok = False

    _log(msg, "OK" if is_ok else "WARN")

    return {
        "ok":            is_ok,
        "executed":      executed,
        "failed":        failed,
        "muted_pending": muted_pending,
        "message":       msg,
    }



# ─────────────────────────────────────────────────────────────────────────────
# CLOSE — CLOSE STRIKE + ITS HEDGE (HARD RULE: ALWAYS TOGETHER WITH DELAY)
# ─────────────────────────────────────────────────────────────────────────────

def process_pending_closes() -> int:
    """
    Checks all active blocks for HEDGE strikes in 'PENDING_CLOSE' status.
    If the scheduled delay (60s) has passed, executes the exit order (sell the hedge)
    reconciles the position, and marks the strike as CLOSED.
    Returns: count of successfully closed hedges.
    """
    closed_count = 0
    try:
        # Fix #3: Scan ACTIVE and EXPIRED blocks — a block may expire while
        # a hedge is still in PENDING_CLOSE. We must not skip those hedges.
        all_blocks = db.get_all_blocks()  # All statuses
        active_or_expired = [b for b in all_blocks if b["status"] in ("ACTIVE", "EXPIRED")]
        for b in active_or_expired:
            strikes = db.get_strikes_by_block(b["block_id"])
            for s in strikes:
                if s["status"] != "PENDING_CLOSE":
                    continue
                
                strike_id = s["strike_id"]
                close_time_str = db.get(f"pending_close_time_{strike_id}", "0")
                try:
                    close_time = float(close_time_str)
                except ValueError:
                    close_time = 0.0
                
                if close_time <= 0:
                    close_time = time.time()
                    db.set(f"pending_close_time_{strike_id}", str(close_time))
                
                if time.time() >= close_time:
                    _log(f"Background engine closing pending hedge strike {strike_id} | {s['strike_price']} {s['option_type']} HEDGE_BUY", "EXIT")
                    
                    open_leg = db.get_open_leg(strike_id)
                    if not open_leg:
                        db.update_strike_status(strike_id, "CLOSED")
                        conn = db._conn()
                        conn.execute("DELETE FROM settings WHERE key=?", (f"pending_close_time_{strike_id}",))
                        conn.commit()
                        conn.close()
                        _log(f"Pending close: Hedge strike {strike_id} has no open leg. Marked as CLOSED.", "INFO")
                        continue
                    
                    hedge_symbol = _resolve_symbol(s)
                    if hedge_symbol:
                        lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
                        qty = s["lots"] * lot_size
                        
                        order_id, filled = kite_executor.execute_sell_and_confirm(
                            trading_symbol = hedge_symbol["trading_symbol"],
                            symbol_token   = hedge_symbol["token"],
                            qty            = qty,
                        )
                        
                        if filled:
                            entry_price = open_leg.get("entry_price", s["anchor_price"])
                            hedge_close_price = kite_executor.get_order_fill_price(order_id)
                            if hedge_close_price <= 0:
                                hedge_close_price = kite_executor.get_ltp(hedge_symbol["token"], hedge_symbol["trading_symbol"])
                            if hedge_close_price <= 0:
                                hedge_close_price = s["anchor_price"]
                                
                            hedge_pnl = (hedge_close_price - entry_price) * s["lots"] * lot_size
                            db.close_leg(open_leg["leg_id"], hedge_close_price, hedge_pnl)
                            
                            db.log_trade(
                                block_id     = s["block_id"],
                                strike_id    = strike_id,
                                action       = "HEDGE_EXIT",
                                price        = hedge_close_price,
                                lots         = s["lots"],
                                order_status = "SUCCESS",
                            )
                            
                            conn = db._conn()
                            conn.execute("DELETE FROM settings WHERE key=?", (f"pending_close_time_{strike_id}",))
                            conn.commit()
                            conn.close()
                            
                            block_num = b["block_number"]
                            tg.send(
                                f"🛡️ <b>HEDGE DELAYED CLOSE COMPLETE</b>\n"
                                f"Block {block_num} | Strike {s['strike_price']} {s['option_type']} HEDGE_BUY\n"
                                f"Hedge Exit: ₹{hedge_close_price:.2f} (Entry: ₹{entry_price:.2f})\n"
                                f"Net P&L: <b>Rs {hedge_pnl:+.2f}</b>\n"
                                f"Status: Closed successfully by background queue."
                            )
                            _log(f"Delayed hedge close confirmed: {hedge_symbol['trading_symbol']} @ Rs{hedge_close_price:.2f}", "OK")
                            closed_count += 1
                        else:
                            last_warn_time = float(db.get(f"warn_close_time_{strike_id}", "0"))
                            if time.time() - last_warn_time > 300:
                                tg.send(f"⚠️ <b>HEDGE DELAYED CLOSE FAILED</b>\nFailed to execute close order for hedge strike {strike_id}! Will retry in background.")
                                db.set(f"warn_close_time_{strike_id}", str(time.time()))
                            _log(f"WARNING: Background hedge exit SELL failed for strike {strike_id}. Retrying next cycle...", "WARN")
                    else:
                        _log(f"WARNING: Background close cannot resolve hedge symbol for strike {strike_id}.", "WARN")
    except Exception as e:
        _log(f"Error in process_pending_closes: {e}", "ERROR")
    return closed_count


def close_strike(strike_id: int, close_hedge: bool = True) -> dict:
    """
    Closes a SELL strike immediately, and schedules the linked hedge strike to close
    after 1 minute (if close_hedge is True) via the DB pending queue.

    HARD RULE (Blueprint Step 5 + Margin Protection):
      - Sequence: BUY-to-cover short FIRST -> confirm -> wait 1 min -> SELL hedge to close
      - Other strikes in same block = UNTOUCHED
      - Realized P&L calculated and logged
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}

    if strike["status"] in ("CLOSED", "CLOSING"):
        return {"ok": False, "message": f"Strike {strike_id} is already {strike['status']} -- skipping duplicate close."}

    if strike["status"] != "OPEN":
        return {"ok": False, "message": f"Strike {strike_id} is {strike['status']} -- only OPEN strikes can be closed."}

    if strike["leg_type"] != "SELL":
        return {"ok": False, "message": "Use close_strike() only on SELL strikes. Hedge closes automatically with it."}

    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    qty      = strike["lots"] * lot_size

    block = db.get_block(strike["block_id"])
    block_num = block["block_number"] if block else "?"

    # Atomic Pre-Order Lock: Mark strike status as 'CLOSING' in DB immediately to prevent concurrent calls
    db.update_strike_status(strike_id, "CLOSING")

    _log(f"Closing Strike {strike_id}: Block {block_num} | {strike['strike_price']} {strike['option_type']} SELL | Qty={qty}", "EXIT")

    # ── Step 1: BUY-to-cover the short option ────────────────────────────────
    sell_symbol = _resolve_symbol(strike)
    if not sell_symbol:
        db.update_strike_status(strike_id, "OPEN")
        return {"ok": False, "message": f"Cannot resolve symbol for sell strike {strike_id}."}

    cover_order_id, cover_filled = kite_executor.execute_buy_and_confirm(
        trading_symbol = sell_symbol["trading_symbol"],
        symbol_token   = sell_symbol["token"],
        qty            = qty,
    )

    if not cover_filled:
        db.update_strike_status(strike_id, "OPEN")
        return {
            "ok":     False,
            "message": f"URGENT: Buy-to-cover for strike {strike_id} FAILED. Position may still be open!",
        }

    _log(f"Buy-to-cover confirmed: {sell_symbol['trading_symbol']} | Order: {cover_order_id}", "OK")

    # Fix #5: Explicitly mark sell strike as CLOSED right after confirmed cover,
    # regardless of whether open_leg exists in DB (covers reconciliation edge cases).
    db.update_strike_status(strike_id, "CLOSED")

    # Get open leg to calculate P&L
    open_leg       = db.get_open_leg(strike_id)
    entry_price    = open_leg.get("entry_price", strike["anchor_price"]) if open_leg else strike["anchor_price"]
    sell_close_price = kite_executor.get_order_fill_price(cover_order_id)
    if sell_close_price <= 0:
        sell_close_price = kite_executor.get_ltp(sell_symbol["token"], sell_symbol["trading_symbol"])
    if sell_close_price <= 0:
        sell_close_price = strike["anchor_price"]

    # Sell P&L: (entry_price - exit_price) * lots * lot_size
    sell_pnl = (entry_price - sell_close_price) * strike["lots"] * lot_size

    # Close sell leg in DB
    if open_leg:
        db.close_leg(open_leg["leg_id"], sell_close_price, sell_pnl)

    # Log trade
    db.log_trade(
        block_id     = strike["block_id"],
        strike_id    = strike_id,
        action       = "EXIT",
        price        = sell_close_price,
        lots         = strike["lots"],
        order_status = "SUCCESS",
    )

    # ── Step 2: Schedule delayed hedge close (if close_hedge is True) ────────
    hedge_strike_id   = strike.get("hedge_strike_id")
    hedge_strike      = db.get_strike(hedge_strike_id) if hedge_strike_id else None

    if close_hedge and hedge_strike and hedge_strike["status"] == "OPEN":
        # Mark the hedge strike as PENDING_CLOSE immediately in DB to prevent re-entry trigger
        db.update_strike_status(hedge_strike_id, "PENDING_CLOSE")
        
        # Store scheduled time to close (current time + 60 seconds) in DB settings
        db.set(f"pending_close_time_{hedge_strike_id}", str(time.time() + 60))
        
        _log(f"Hedge strike {hedge_strike_id} marked as PENDING_CLOSE. Will close in 60s in background.", "EXIT")
    elif not hedge_strike:
        _log(f"No linked hedge for strike {strike_id}. Closing sell only.", "WARN")

    # ── Total realized P&L (For the immediately closed SELL leg) ─────────────
    realized_pnl = round(sell_pnl, 2)

    _log(
        f"Strike {strike_id} CLOSED | Sell P&L=Rs{sell_pnl:.2f} | Delayed hedge scheduled",
        "OK"
    )

    return {
        "ok":               True,
        "sell_close_price": sell_close_price,
        "sell_pnl":         round(sell_pnl, 2),
        "realized_pnl":     realized_pnl,
        "message":          (
            f"Strike {strike['strike_price']} {strike['option_type']} closed. "
            f"Hedge scheduled to close in 1 minute. Sell P&L: Rs{realized_pnl:+.2f}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXPIRY MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def check_expiries() -> list:
    """
    Auto-expires blocks whose expiry_date has passed.
    Called by main.py background loop.
    Returns: list of expired block_ids
    """
    expired = db.check_and_expire_blocks()
    if expired:
        _log(f"Auto-expired {len(expired)} block(s): {expired}", "EXPIRY")
    return expired


def get_portfolio_status() -> dict:
    """
    Returns a quick portfolio status snapshot.
    Used by dashboard header bar.
    """
    active_blocks  = db.get_all_blocks(status_filter="ACTIVE")
    open_strikes   = 0
    for b in active_blocks:
        strikes       = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
        open_strikes += len(strikes)
    return {
        "active_blocks":      len(active_blocks),
        "total_open_strikes": open_strikes,
        "paper_mode":         False,
        "algo_running":       db.get("algo_running", "ON") == "ON",
        "last_cycle_time":    db.get("last_cycle_time", "Never"),
    }


def update_strike_anchor_price(strike_id: int, anchor_price: float) -> dict:
    """Updates the anchor price for a strike."""
    ok = db.update_strike_anchor_price(strike_id, anchor_price)
    if ok:
        return {"ok": True, "message": f"Anchor updated for Strike {strike_id} to Rs{anchor_price:.2f}."}
    return {"ok": False, "message": f"Failed to update anchor for Strike {strike_id}."}


def close_hedge_strike_now(strike_id: int) -> dict:
    """
    Closes an open HEDGE_BUY strike immediately on the broker and locks realized profit.
    Returns: {"ok": bool, "message": str, "fill_price": float, "pnl": float}
    """
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}
    if strike["leg_type"] != "HEDGE_BUY":
        return {"ok": False, "message": "Only hedge strikes can be closed with this function."}
    if strike["status"] not in ("OPEN", "PENDING_CLOSE"):
        return {"ok": False, "message": f"Strike status is {strike['status']}. Only OPEN hedges can be closed."}

    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    qty      = strike["lots"] * lot_size

    # Resolve symbol
    hedge_symbol = _resolve_symbol(strike)
    if not hedge_symbol:
        return {"ok": False, "message": f"Cannot resolve symbol for hedge strike {strike_id}."}

    # Atomic Pre-Order Lock
    db.update_strike_status(strike_id, "CLOSING")

    _log(f"Closing Hedge Strike {strike_id} immediately: {strike['strike_price']} {strike['option_type']} HEDGE_BUY | Qty={qty}", "EXIT")

    order_id, filled = kite_executor.execute_sell_and_confirm(
        trading_symbol = hedge_symbol["trading_symbol"],
        symbol_token   = hedge_symbol["token"],
        qty            = qty,
    )

    if not filled:
        db.update_strike_status(strike_id, "OPEN")
        return {"ok": False, "message": f"Hedge exit SELL order failed on broker for strike {strike_id}."}

    # Mark strike as CLOSED
    db.update_strike_status(strike_id, "CLOSED")

    # Clean up any scheduled pending close entry
    conn = db._conn()
    conn.execute("DELETE FROM settings WHERE key=?", (f"pending_close_time_{strike_id}",))
    conn.commit()
    conn.close()

    open_leg    = db.get_open_leg(strike_id)
    entry_price = open_leg.get("entry_price", strike["anchor_price"]) if open_leg else strike["anchor_price"]
    hedge_close_price = kite_executor.get_order_fill_price(order_id)
    if hedge_close_price <= 0:
        hedge_close_price = kite_executor.get_ltp(hedge_symbol["token"], hedge_symbol["trading_symbol"])
    if hedge_close_price <= 0:
        hedge_close_price = strike["anchor_price"]

    # Hedge P&L: (exit_price - entry_price) * lots * lot_size
    hedge_pnl = (hedge_close_price - entry_price) * strike["lots"] * lot_size
    if open_leg:
        db.close_leg(open_leg["leg_id"], hedge_close_price, hedge_pnl)

    db.log_trade(
        block_id     = strike["block_id"],
        strike_id    = strike_id,
        action       = "HEDGE_EXIT",
        price        = hedge_close_price,
        lots         = strike["lots"],
        order_status = "SUCCESS",
    )

    block     = db.get_block(strike["block_id"])
    block_num = block["block_number"] if block else "?"

    tg.send(
        f"🎯 <b>HEDGE PROFIT LOCKED & CLOSED</b>\n"
        f"Block {block_num} | Strike {strike['strike_price']} {strike['option_type']} HEDGE_BUY\n"
        f"Exit Price: ₹{hedge_close_price:.2f} (Entry: ₹{entry_price:.2f})\n"
        f"Realized P&L: <b>Rs {hedge_pnl:+.2f}</b>\n"
        f"Status: Closed immediately on broker to lock profit."
    )

    _log(f"Hedge {strike_id} closed immediately: {hedge_symbol['trading_symbol']} @ Rs{hedge_close_price:.2f} | P&L=Rs{hedge_pnl:.2f}", "OK")

    return {
        "ok":         True,
        "message":    f"Hedge {strike['strike_price']} {strike['option_type']} closed @ ₹{hedge_close_price:.2f}! Locked Profit: Rs {hedge_pnl:+.2f}",
        "fill_price": hedge_close_price,
        "pnl":        round(hedge_pnl, 2),
    }


def close_hedge_strike_only(strike_id: int) -> dict:
    """Closes an open HEDGE strike immediately to lock profit (with pending queue fallback)."""
    strike = db.get_strike(strike_id)
    if not strike:
        return {"ok": False, "message": f"Strike {strike_id} not found."}
    if strike["leg_type"] != "HEDGE_BUY":
        return {"ok": False, "message": "Only hedge strikes can be closed with this function."}
    if strike["status"] != "OPEN":
        return {"ok": False, "message": f"Strike status is {strike['status']}. Only OPEN hedges can be closed."}

    # Attempt immediate close on broker
    res = close_hedge_strike_now(strike_id)
    if res["ok"]:
        return res

    # If immediate execution failed, schedule via pending queue fallback
    db.update_strike_status(strike_id, "PENDING_CLOSE")
    db.set(f"pending_close_time_{strike_id}", str(time.time()))
    _log(f"Manual Hedge Close fallback scheduled: Strike {strike_id} ({strike['strike_price']} {strike['option_type']})", "EXIT")
    return {
        "ok": True,
        "message": f"Hedge strike {strike['strike_price']} {strike['option_type']} scheduled to close in the background."
    }


# --- FEATURE A: HEDGE ROLLOVER ---

def rollover_hedge(
    sell_strike_id:         int,
    new_hedge_strike_price: int,
    new_hedge_expiry:       str,
    new_hedge_lots:         int,
    new_hedge_option_type:  str,
) -> dict:
    """
    Rolls over the hedge linked to a SELL strike.

    Sequence:
      Step 1 - Validate sell + old hedge are OPEN.
      Step 2 - Close old hedge immediately on broker.
      Step 3 - Create new HEDGE_BUY strike in DB.
      Step 4 - Buy new hedge on broker.
      Step 5 - Re-link sell strike to new hedge.
      Step 6 - Send Telegram alerts.

    Returns: {"ok": bool, "message": str, "new_hedge_strike_id": int or None}
    """
    sell_strike = db.get_strike(sell_strike_id)
    if not sell_strike:
        return {"ok": False, "message": f"Sell strike {sell_strike_id} not found."}
    if sell_strike["leg_type"] != "SELL":
        return {"ok": False, "message": "rollover_hedge() can only be called on SELL strikes."}
    if sell_strike["status"] != "OPEN":
        return {"ok": False, "message": f"Sell must be OPEN. Current: {sell_strike['status']}."}

    old_hedge_id = sell_strike.get("hedge_strike_id")
    old_hedge    = db.get_strike(old_hedge_id) if old_hedge_id else None
    block        = db.get_block(sell_strike["block_id"])
    block_num    = block["block_number"] if block else "?"
    lot_size     = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))

    # Step 1 - Validate old hedge
    if not old_hedge:
        _log(f"[ROLLOVER] No linked hedge for sell {sell_strike_id}. Buying fresh.", "WARN")
        old_hedge_symbol = "None"
    elif old_hedge["status"] == "CLOSED":
        _log(f"[ROLLOVER] Linked old hedge {old_hedge_id} is already CLOSED in DB. Skipping broker close order.", "WARN")
        old_hedge_symbol = (
            f"{old_hedge['strike_price']} {old_hedge['option_type']} "
            f"(exp: {old_hedge.get('expiry_date', 'N/A')}) [Already CLOSED]"
        )
    else:
        if old_hedge["status"] not in ("OPEN", "PENDING_CLOSE"):
            return {
                "ok": False,
                "message": f"Old hedge status is {old_hedge['status']} -- must be OPEN or PENDING_CLOSE."
            }
        old_hedge_symbol = (
            f"{old_hedge['strike_price']} {old_hedge['option_type']} "
            f"(exp: {old_hedge.get('expiry_date', 'N/A')})"
        )

    tg.alert_rollover_started(block_number=block_num, old_hedge=old_hedge_symbol, new_expiry=new_hedge_expiry)
    _log(f"[ROLLOVER] Block {block_num}: rolling hedge for sell {sell_strike_id}. Old: {old_hedge_symbol}", "ORDER")

    # Step 2 - Close old hedge on broker
    if old_hedge and old_hedge["status"] == "OPEN":
        old_qty      = old_hedge["lots"] * lot_size
        old_sym_info = _resolve_symbol(old_hedge)
        if not old_sym_info:
            return {"ok": False, "message": f"Cannot resolve old hedge symbol. Aborting rollover."}
        _log(f"[ROLLOVER] Closing old hedge: {old_sym_info['trading_symbol']} qty={old_qty}", "ORDER")
        close_order_id, close_filled = kite_executor.execute_sell_and_confirm(
            trading_symbol = old_sym_info["trading_symbol"],
            symbol_token   = old_sym_info["token"],
            qty            = old_qty,
        )
        if not close_filled:
            tg.alert_rollover_failed(block_num, f"Old hedge close failed (order {close_order_id}). Rollover aborted.")
            return {"ok": False, "message": f"Old hedge close FAILED (order {close_order_id}). Rollover aborted."}
        close_price = kite_executor.get_order_fill_price(close_order_id)
        if close_price <= 0:
            close_price = kite_executor.get_ltp(old_sym_info["token"], old_sym_info["trading_symbol"])
        if close_price <= 0:
            close_price = float(old_hedge.get("anchor_price", 0.0))
        open_leg    = db.get_open_leg(old_hedge_id)
        entry_price = open_leg.get("entry_price", old_hedge["anchor_price"]) if open_leg else old_hedge["anchor_price"]
        hedge_pnl   = (close_price - entry_price) * -old_qty
        if open_leg:
            db.close_leg(open_leg["leg_id"], close_price, hedge_pnl)
        db.update_strike_status(old_hedge_id, "CLOSED")
        _log(f"[ROLLOVER] Old hedge closed @ Rs{close_price:.2f} | PnL: Rs{hedge_pnl:.2f}", "OK")

    # Step 3 - Create new HEDGE_BUY in DB
    new_hedge_res = add_strike_to_block(
        block_id     = sell_strike["block_id"],
        strike_price = new_hedge_strike_price,
        option_type  = new_hedge_option_type,
        leg_type     = "HEDGE_BUY",
        anchor_price = 0.0,
        lots         = new_hedge_lots,
        expiry_date  = new_hedge_expiry,
    )
    if not new_hedge_res["ok"]:
        tg.alert_rollover_failed(block_num, f"New hedge DB creation failed: {new_hedge_res['message']}")
        return {"ok": False, "message": f"New hedge DB failed: {new_hedge_res['message']}. Old hedge closed -- buy manually!"}

    new_hedge_strike_id = new_hedge_res["strike_id"]
    _log(f"[ROLLOVER] New hedge in DB: id={new_hedge_strike_id} {new_hedge_strike_price} {new_hedge_option_type} exp={new_hedge_expiry}", "ORDER")

    # Step 4 - Buy new hedge on broker
    new_qty = new_hedge_lots * lot_size
    db.try_set_strike_executing(new_hedge_strike_id)
    new_hedge_rec = db.get_strike(new_hedge_strike_id)
    buy_result    = _execute_buy_leg(new_hedge_rec, new_qty)

    if not buy_result["ok"]:
        db.update_strike_status(new_hedge_strike_id, "PENDING")
        tg.alert_naked_short_risk(block_num, sell_strike["strike_price"], sell_strike["option_type"])
        tg.alert_rollover_failed(block_num, f"NEW HEDGE BUY FAILED. SELL IS UNHEDGED!")
        return {
            "ok": False,
            "message": (
                f"CRITICAL: Old hedge closed but new hedge BUY failed. "
                f"Sell {sell_strike['strike_price']} {sell_strike['option_type']} is UNHEDGED! "
                f"Strike #{new_hedge_strike_id} is PENDING -- buy manually on broker."
            ),
            "new_hedge_strike_id": new_hedge_strike_id,
        }

    db.update_strike_anchor_price(new_hedge_strike_id, buy_result["fill_price"])
    _log(f"[ROLLOVER] New hedge bought @ Rs{buy_result['fill_price']:.2f} | Order: {buy_result['order_id']}", "OK")

    # Step 5 - Re-link
    if old_hedge_id:
        db.unlink_hedge(old_hedge_id)
    link_hedge_to_sell(sell_strike_id, new_hedge_strike_id)

    # Step 6 - Telegram
    new_sym_info = _resolve_symbol(db.get_strike(new_hedge_strike_id))
    new_symbol   = new_sym_info["trading_symbol"] if new_sym_info else f"{new_hedge_strike_price}{new_hedge_option_type}"
    tg.alert_rollover_complete(
        block_number = block_num,
        old_symbol   = old_hedge_symbol,
        new_symbol   = new_symbol,
        new_expiry   = new_hedge_expiry,
    )
    _log(f"[ROLLOVER] SUCCESS: Block {block_num} | {old_hedge_symbol} -> {new_symbol} @ Rs{buy_result['fill_price']:.2f}", "OK")

    return {
        "ok": True,
        "message": (
            f"Rollover complete! Old hedge closed. "
            f"New hedge {new_hedge_strike_price} {new_hedge_option_type} ({new_hedge_expiry}) "
            f"bought @ Rs{buy_result['fill_price']:.2f}."
        ),
        "new_hedge_strike_id": new_hedge_strike_id,
    }


def sync_positions_with_broker() -> int:
    """
    Fetches open holdings from broker and matches them against database OPEN strikes.
    If a strike is OPEN in DB but has quantity = 0 or is missing from broker holdings,
    it means the user closed it manually. We update the DB status to CLOSED.
    Returns: count of manually closed strikes reconciled.
    """
    if db.get("algo_running", "ON") != "ON":
        return 0

    try:
        # 1. Fetch live holdings/positions from Zerodha
        broker_positions = kite_executor.get_positions()

        # Empty Response Guard: If broker_positions is empty/None (API glitch or empty holdings),
        # skip reconciliation to avoid accidental database wipe.
        if broker_positions is None or len(broker_positions) == 0:
            _log("[SYNC] Received empty broker positions list. Skipping reconciliation guard to avoid accidental database wipe.", "WARN")
            return 0

        # Build a map of broker positions for easy lookup: {token/tradingsymbol: qty}
        broker_qtys = {}
        for pos in broker_positions:
            token = pos.get("instrument_token") or pos.get("tradingsymbol")
            if token:
                qty = float(pos.get("quantity", 0))
                broker_qtys[str(token)] = qty

        # 2. Get all ACTIVE blocks
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        reconciled_count = 0

        for b in active_blocks:
            # Get all OPEN strikes for this block
            open_strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")

            for s in open_strikes:
                # Resolve the token for this strike
                symbol_info = _resolve_symbol(s)
                if not symbol_info or not symbol_info.get("token"):
                    continue

                token = str(symbol_info["token"])
                trading_symbol = str(symbol_info["trading_symbol"])

                # Check if this token exists in broker positions
                broker_qty = broker_qtys.get(token)
                if broker_qty is None:
                    broker_qty = broker_qtys.get(trading_symbol, 0.0)

                # Fetch leg record to check entry time BEFORE determining is_closed
                open_leg = db.get_open_leg(s["strike_id"])

                # API Delay Cooldown Guard: Skip recently entered legs (< 5 mins) to prevent race condition before broker registers it
                if open_leg and open_leg.get("entry_time"):
                    try:
                        from datetime import datetime
                        import pytz
                        IST = pytz.timezone("Asia/Kolkata")
                        entry_dt = datetime.strptime(open_leg["entry_time"], "%Y-%m-%d %H:%M:%S")
                        entry_dt = IST.localize(entry_dt)
                        now_dt = datetime.now(IST)
                        elapsed = (now_dt - entry_dt).total_seconds()
                        if elapsed < 300:
                            _log(f"[SYNC] Skipping sync-close for recently entered strike {s['strike_id']} (elapsed: {elapsed:.1f}s < 300s)", "INFO")
                            continue
                    except Exception as parse_err:
                        _log(f"[SYNC] Error parsing entry time for strike {s['strike_id']}: {parse_err}", "ERROR")

                # A position is manually closed if:
                # - It is not in the broker positions list (broker_qty == 0)
                # - Or the direction of position is reversed/mismatched:
                #   - For SELL strikes: quantity should be negative (net short)
                #   - For HEDGE_BUY strikes: quantity should be positive (net long)
                is_closed = False
                if broker_qty == 0.0:
                    is_closed = True
                elif s["leg_type"] == "SELL" and broker_qty > 0.0:
                    is_closed = True
                elif s["leg_type"] == "HEDGE_BUY" and broker_qty < 0.0:
                    is_closed = True

                if is_closed:
                    _log(f"[SYNC] Strike {s['strike_id']} ({s['strike_price']} {s['option_type']} {s['leg_type']}) was closed manually at broker. Syncing DB...", "WARN")

                    # Update leg and strike status to CLOSED in DB
                    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))

                    # Use current LTP or anchor as exit price
                    exit_price = kite_executor.get_ltp(symbol_info["token"], symbol_info["trading_symbol"])
                    if exit_price <= 0:
                        exit_price = s["anchor_price"]

                    if s["leg_type"] == "SELL":
                        entry_price = open_leg.get("entry_price", s["anchor_price"]) if open_leg else s["anchor_price"]
                        pnl = (entry_price - exit_price) * s["lots"] * lot_size
                    else:
                        entry_price = open_leg.get("entry_price", s["anchor_price"]) if open_leg else s["anchor_price"]
                        pnl = (exit_price - entry_price) * s["lots"] * lot_size

                    if open_leg:
                        db.close_leg(open_leg["leg_id"], exit_price, pnl)
                    else:
                        db.update_strike_status(s["strike_id"], "CLOSED")

                    db.log_trade(
                        block_id     = s["block_id"],
                        strike_id    = s["strike_id"],
                        action       = "EXIT" if s["leg_type"] == "SELL" else "HEDGE_EXIT",
                        price        = exit_price,
                        lots         = s["lots"],
                        order_status = "SUCCESS",
                    )

                    # Send Telegram alert
                    leg_label = "SELL" if s["leg_type"] == "SELL" else "Hedge"
                    alert_msg = (
                        f"🔄 <b>MANUAL EXIT DETECTED & SYNCED</b> 🔄\n"
                        f"Block {b['block_number']} | Strike <b>{s['strike_price']} {s['option_type']} {leg_label}</b>\n"
                        f"Status: Strike was closed manually at broker app/web.\n"
                        f"Action: Syncing SQLite DB status to <b>CLOSED</b>.\n"
                        f"Calculated PnL: Rs{pnl:+.2f}"
                    )
                    tg.send(alert_msg)
                    reconciled_count += 1

        return reconciled_count
    except Exception as e:
        _log(f"Exception in sync_positions_with_broker: {e}", "ERROR")
        return 0


def run_daily_strike_reset() -> int:
    """
    At the start of a trading day, scans all ACTIVE blocks.
    For any strike in these blocks that is in 'CLOSED' status,
    resets its status (and its linked hedge strike status) back to 'PENDING'.
    
    Returns the count of strikes reset.
    """
    from datetime import datetime
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    
    reset_count = 0
    try:
        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        for b in active_blocks:
            strikes = db.get_strikes_by_block(b["block_id"])
            for s in strikes:
                if s["leg_type"] == "SELL" and s["status"] == "CLOSED":
                    # Double check: is there any exit time from a previous day?
                    legs = db.get_legs_by_strike(s["strike_id"])
                    is_closed_before_today = False
                    today_str = datetime.now(IST).strftime("%Y-%m-%d")
                    if legs:
                        # db.get_legs_by_strike returns legs ordered by leg_id DESC (most recent first)
                        most_recent_leg = legs[0]
                        exit_time = most_recent_leg.get("exit_time", "")
                        if exit_time:
                            exit_date = exit_time.split(" ")[0]
                            if exit_date != today_str:
                                is_closed_before_today = True
                    
                    if is_closed_before_today or not legs:
                        # Reset both the SELL strike and its linked HEDGE_BUY strike to PENDING
                        db.update_strike_status(s["strike_id"], "PENDING")
                        reset_count += 1
                        _log(f"[DAILY-RESET] Reset SELL strike {s['strike_id']} ({s['strike_price']} {s['option_type']}) to PENDING.", "INFO")
                        
                        hedge_id = s.get("hedge_strike_id")
                        if hedge_id:
                            db.update_strike_status(hedge_id, "PENDING")
                            reset_count += 1
                            _log(f"[DAILY-RESET] Reset linked HEDGE strike {hedge_id} to PENDING.", "INFO")
    except Exception as e:
        _log(f"Error in run_daily_strike_reset: {e}", "ERROR")
    return reset_count


def rearm_block_strikes(block_id: int) -> dict:
    """
    Manually re-arms all CLOSED strikes in an ACTIVE block back to 'PENDING'.
    Also resets linked hedge strikes back to 'PENDING'.
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}
    
    strikes = db.get_strikes_by_block(block_id)
    rearmed_count = 0
    for s in strikes:
        if s["status"] == "CLOSED":
            db.update_strike_status(s["strike_id"], "PENDING")
            rearmed_count += 1
            _log(f"[REARM] Re-armed strike {s['strike_id']} ({s['strike_price']} {s['option_type']} {s['leg_type']}) to PENDING.", "OK")
            
    if rearmed_count > 0:
        return {"ok": True, "count": rearmed_count, "message": f"Successfully re-armed {rearmed_count} strike(s) in Block {block['block_number']} to PENDING."}
    else:
        return {"ok": False, "message": f"No CLOSED strikes found to re-arm in Block {block['block_number']}."}


def kill_block(block_id: int) -> dict:
    """
    Kill Switch for a block:
    1. Attempts to exit all open strikes (SELL and HEDGE_BUY) in the block.
    2. Force deletes the block from the database regardless of exit success.
    
    Returns: {"ok": bool, "message": str}
    """
    block = db.get_block(block_id)
    if not block:
        return {"ok": False, "message": f"Block {block_id} not found."}
    
    block_num = block["block_number"]
    expiry = block["expiry_date"]
    _log(f"KILL SWITCH TRIGGERED for Block {block_num} (ID: {block_id})", "WARN")
    
    # Send TG alert about Kill Switch initiation
    tg.send_silent(
        f"⚠️ <b>KILL SWITCH INITIATED</b>\n"
        f"Block {block_num} ({expiry})\n"
        f"Attempting to exit all open positions immediately..."
    )
    
    # Retrieve all strikes in the block
    strikes = db.get_strikes_by_block(block_id)
    open_strikes = [s for s in strikes if s["status"] in ("OPEN", "PENDING_CLOSE")]
    
    exited_strikes = []
    failed_strikes = []
    lot_size = int(db.get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    
    # Separate into SELL and HEDGE_BUY strikes
    sell_strikes = [s for s in open_strikes if s["leg_type"] == "SELL"]
    hedge_strikes = [s for s in open_strikes if s["leg_type"] == "HEDGE_BUY"]
    
    # Exit SELL strikes first (highest risk)
    for s in sell_strikes:
        qty = s["lots"] * lot_size
        symbol_info = _resolve_symbol(s)
        if not symbol_info:
            err_msg = f"{s['strike_price']} {s['option_type']} SELL (symbol unresolved)"
            failed_strikes.append(err_msg)
            _log(f"Kill Switch: {err_msg}", "ERROR")
            continue
            
        trading_symbol = symbol_info["trading_symbol"]
        token = symbol_info["token"]
        _log(f"Kill Switch: Closing short leg {trading_symbol} qty={qty}", "EXIT")
        
        # Execute BUY order to cover the short
        order_id, filled = kite_executor.execute_buy_and_confirm(
            trading_symbol = trading_symbol,
            symbol_token   = token,
            qty            = qty,
        )
        if filled:
            exited_strikes.append(f"{s['strike_price']} {s['option_type']} SELL")
            _log(f"Kill Switch: Short leg closed. Order: {order_id}", "OK")
        else:
            err_msg = f"{s['strike_price']} {s['option_type']} SELL (exit order failed)"
            failed_strikes.append(err_msg)
            _log(f"Kill Switch: {err_msg}", "ERROR")

    # Exit HEDGE_BUY strikes
    for s in hedge_strikes:
        qty = s["lots"] * lot_size
        symbol_info = _resolve_symbol(s)
        if not symbol_info:
            err_msg = f"{s['strike_price']} {s['option_type']} HEDGE_BUY (symbol unresolved)"
            failed_strikes.append(err_msg)
            _log(f"Kill Switch: {err_msg}", "ERROR")
            continue
            
        trading_symbol = symbol_info["trading_symbol"]
        token = symbol_info["token"]
        _log(f"Kill Switch: Closing hedge leg {trading_symbol} qty={qty}", "EXIT")
        
        # Execute SELL order to close the hedge
        order_id, filled = kite_executor.execute_sell_and_confirm(
            trading_symbol = trading_symbol,
            symbol_token   = token,
            qty            = qty,
        )
        if filled:
            exited_strikes.append(f"{s['strike_price']} {s['option_type']} HEDGE_BUY")
            _log(f"Kill Switch: Hedge leg closed. Order: {order_id}", "OK")
        else:
            err_msg = f"{s['strike_price']} {s['option_type']} HEDGE_BUY (exit order failed)"
            failed_strikes.append(err_msg)
            _log(f"Kill Switch: {err_msg}", "ERROR")

    # Force delete block from DB
    deleted = db.force_delete_block(block_id)
    
    status_msg = f"Block {block_num} has been force-deleted from database."
    if exited_strikes:
        status_msg += f"\n✅ Successfully exited: {', '.join(exited_strikes)}"
    if failed_strikes:
        status_msg += f"\n❌ Failed to exit: {', '.join(failed_strikes)}\n⚠️ URGENT: Please close failed positions manually on Zerodha terminal!"
        
    tg.send_silent(
        f"💥 <b>KILL SWITCH COMPLETE</b>\n"
        f"Block {block_num} ({expiry})\n"
        f"DB Deletion: {'SUCCESS' if deleted else 'FAILED'}\n"
        f"{status_msg}"
    )
    
    if failed_strikes:
        return {
            "ok": deleted,
            "message": f"Block {block_num} deleted. WARNING: Exit orders failed for: {', '.join(failed_strikes)}. Close them manually on Zerodha!"
        }
    
    return {
        "ok": deleted,
        "message": f"Block {block_num} deleted successfully and all positions closed."
    }


