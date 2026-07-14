"""
commodity_engine.py — Zerodha OptionSelling Engine | Commodity Futures Engine Loop
=============================================================================
STRICT STATE MACHINE — Commodity Futures Anchor Edition
15-min closed candle evaluations | 11:00 PM intraday square-off
"""

import time
import socket
import sys
import traceback
import requests
from datetime import datetime
import pytz

import db
import config as cfg
import utils
import telegram_bot as tg
import commodity_executor as executor

IST = pytz.timezone("Asia/Kolkata")


def check_ip_guard() -> bool:
    """Enforces IP Whitelisting."""
    allowed_ip = db.get("ALLOWED_TRADING_IP", "46.224.133.16").strip()
    if allowed_ip.upper() == "ANY":
        return True

    try:
        current_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        allowed_list = [ip.strip() for ip in allowed_ip.split(",")]
        if current_ip not in allowed_list:
            utils.log(f"IP GUARD TRIGGERED (COMMODITY): Current IP {current_ip} not in whitelist {allowed_ip}", "ALERT")
            return False
        return True
    except Exception as e:
        utils.log(f"Failed to check public IP: {e}. Skipping IP guard check.", "WARN")
        return True


def _acquire_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", cfg.COMMODITY_LOCK_PORT))
        return lock
    except OSError:
        print(f"COMMODITY ENGINE ALREADY RUNNING (port {cfg.COMMODITY_LOCK_PORT}). Exiting.")
        sys.exit(1)


def seconds_to_next_15min_candle() -> int:
    """Sleeps until exactly 65 seconds after the next 15-minute boundary."""
    candle_minutes = 15
    now = datetime.now(IST)
    elapsed_in_period = (now.minute % candle_minutes) * 60 + now.second
    seconds_to_boundary = (candle_minutes * 60) - elapsed_in_period
    total_sleep = seconds_to_boundary + 65
    max_sleep = candle_minutes * 60 + 30
    return max(min(total_sleep, max_sleep), 65)


def is_commodity_market_open() -> bool:
    """True if MCX market is open on weekdays (09:00 AM to 11:30 PM IST)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Weekend
        return False
    # MCX Futures trade from 9:00 AM to 11:30 PM (or 11:55 PM in winter)
    open_dt = now.replace(hour=cfg.COMMODITY_MARKET_OPEN_H, minute=cfg.COMMODITY_MARKET_OPEN_M, second=0, microsecond=0)
    close_dt = now.replace(hour=23, minute=30, second=0, microsecond=0)
    return open_dt <= now <= close_dt


def is_commodity_squareoff_time() -> bool:
    """True if it is 11:00 PM IST or later, representing intraday cutoff."""
    now = datetime.now(IST)
    cutoff = now.replace(hour=cfg.COMMODITY_SQUAREOFF_H, minute=cfg.COMMODITY_SQUAREOFF_M, second=0, microsecond=0)
    return now >= cutoff


_first_run = True

def run_one_cycle() -> None:
    global _first_run

    # ── 0. Market closed? ────────────────────────────────────
    if not is_commodity_market_open():
        return

    # ── 1. Check if engine is running ────────────────────────
    algo_state = db.get("comm_engine_running", "OFF")
    if algo_state == "OFF":
        utils.log("[COMMODITIES] Commodity engine paused from dashboard.", "WAIT")
        return

    contract_key = db.get("comm_selected_contract", "")
    if not contract_key:
        utils.log("[COMMODITIES] No commodity contract selected. Configure on dashboard.", "WAIT")
        return

    # ── 2. Force Intraday square-off at 11:00 PM IST ─────────
    carry_forward = db.get("comm_carry_forward", "NO") == "YES"
    trade_active = db.get("comm_position_state", "FLAT") != "FLAT"
    
    if not carry_forward and is_commodity_squareoff_time():
        if trade_active:
            utils.log("[COMMODITIES] 11:00 PM FORCE CLOSE: Squaring off all positions...", "ALERT")
            executor.square_off_all_mcx_positions()
        return

    # ── 3. Fetch live contract LTP ───────────────────────────
    ltp = executor.get_mcx_ltp(contract_key)
    if ltp <= 0:
        utils.log(f"[COMMODITIES] Failed to fetch LTP for contract {contract_key}.", "ERROR")
        return
        
    db.set("comm_current_ltp", str(ltp))
    
    # ── 4. Calculate P&L % & Stop Loss ───────────────────────
    if trade_active:
        entry_price = float(db.get("comm_entry_price", "0.0") or 0.0)
        pos_state = db.get("comm_position_state", "FLAT")
        if entry_price > 0:
            if pos_state == "LONG":
                pnl_pct = ((ltp - entry_price) / entry_price) * 100
            elif pos_state == "SHORT":
                pnl_pct = ((entry_price - ltp) / entry_price) * 100
            else:
                pnl_pct = 0.0
                
            db.set("comm_unrealized_pnl_pct", str(round(pnl_pct, 2)))
            
            # Check Stop Loss (SL)
            sl_pct = float(db.get("comm_stop_loss_pct", "0") or 0)
            if sl_pct > 0 and pnl_pct <= -sl_pct:
                utils.log(f"[COMMODITIES] STOP LOSS HIT: {pnl_pct:.2f}% (SL: -{sl_pct}%). Squaring off...", "ALERT")
                tg.send_silent(
                    f"🛑 <b>COMMODITY STOP LOSS HIT</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"P&L dropped to <b>{pnl_pct:.2f}%</b> matching target -{sl_pct}%.\n"
                    f"Squaring off position immediately."
                )
                executor.square_off_all_mcx_positions()
                trade_active = False

    # ── 5. Timing Boundary check: 15-Minute boundary ─────────
    now = datetime.now(IST)
    floor_min = (now.minute // 15) * 15
    curr_15m = f"{now.strftime('%Y-%m-%d')} {now.hour:02d}:{floor_min:02d}"
    last_check = db.get("comm_last_check_candle_time", "")

    if last_check == curr_15m:
        # Already checked this candle boundary
        return

    utils.log(f"[COMMODITIES] Evaluating Anchor Price triggers for boundary {curr_15m}...", "INFO")
    
    # ── 6. Evaluate Anchor prices & trigger trade flips ──────
    anchor_price = float(db.get("comm_anchor_price", "0.0") or 0.0)
    if anchor_price <= 0:
        utils.log("[COMMODITIES] Anchor price not set or <= 0. Skipping trade checks.", "WAIT")
        db.set("comm_last_check_candle_time", curr_15m)
        return

    pos_state = db.get("comm_position_state", "FLAT")
    
    if ltp > anchor_price:
        # We should be LONG
        if pos_state != "LONG":
            utils.log(f"[COMMODITIES] LTP {ltp:.2f} > Anchor {anchor_price:.2f}. Executing LONG Flip...", "TRADE")
            executor.execute_commodity_flip("LONG")
    elif ltp < anchor_price:
        # We should be SHORT
        if pos_state != "SHORT":
            utils.log(f"[COMMODITIES] LTP {ltp:.2f} < Anchor {anchor_price:.2f}. Executing SHORT Flip...", "TRADE")
            executor.execute_commodity_flip("SHORT")

    db.set("comm_last_check_candle_time", curr_15m)


def main():
    lock = _acquire_lock()

    print("=" * 62)
    print("  ⚓ ZERODHA COMMODITY EXTENSION  —  MCX FUTURES ENGINE  ")
    print("=" * 62)
    print("  Rule 1: Isolated database prefixed state keys")
    print("  Rule 2: 15-Minute candle boundary evaluation")
    print("  Rule 3: Reversal flips executed using double lot sizes")
    print("  Rule 4: Intraday square-off at 11:00 PM IST sharp")
    print("=" * 62)

    # 1. IP Whitelist check on startup
    if not check_ip_guard():
        utils.log("Startup IP Whitelist check failed. Commodity engine exiting.", "WARN")
        sys.exit(1)

    _now = datetime.now(IST)
    last_heartbeat_slot = (_now.hour * 4) + (_now.minute // 15)
    last_loop_log = 0.0

    while True:
        try:
            algo_running = db.get("comm_engine_running", "OFF") == "ON"
            
            if algo_running and is_commodity_market_open():
                now = datetime.now(IST)
                curr_slot = (now.hour * 4) + (now.minute // 15)
                
                if curr_slot != last_heartbeat_slot:
                    # Send Commodity Heartbeat
                    contract_key = db.get("comm_selected_contract", "")
                    ltp = float(db.get("comm_current_ltp", "0") or 0)
                    anchor = float(db.get("comm_anchor_price", "0") or 0)
                    pos_state = db.get("comm_position_state", "FLAT")
                    pnl_pct = float(db.get("comm_unrealized_pnl_pct", "0") or 0)
                    entry_p = float(db.get("comm_entry_price", "0") or 0)
                    
                    tg.send_silent(
                        f"🤖 <b>COMMODITY ENGINE HEARTBEAT</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"<b>Status:</b> LIVE & ACTIVE\n"
                        f"<b>Contract:</b> {contract_key}\n"
                        f"<b>LTP:</b> ₹{ltp:.2f} | <b>Anchor:</b> ₹{anchor:.2f}\n"
                        f"<b>Position:</b> {pos_state} " + (f"(P&L: {pnl_pct:.2f}% | Entry: ₹{entry_p:.2f})" if pos_state != "FLAT" else "")
                    )
                    last_heartbeat_slot = curr_slot

                run_one_cycle()
                
                # Log loop state only once every 5 minutes to avoid log spamming
                now_ts = time.time()
                if now_ts - last_loop_log > 300:
                    utils.log("[COMMODITIES] Engine check complete. Sleeping 10s...", "WAIT")
                    last_loop_log = now_ts
                    
            time.sleep(10)

        except KeyboardInterrupt:
            utils.log("Commodity engine stopped by user.", "INFO")
            break
        except Exception as e:
            utils.log(f"COMMODITY ENGINE ERROR: {e}", "ERROR")
            traceback.print_exc()
            tg.send_silent(f"🚨 <b>COMMODITY ENGINE ERROR</b>\nError: {str(e)[:200]}")
            time.sleep(30)

    lock.close()


if __name__ == "__main__":
    main()
