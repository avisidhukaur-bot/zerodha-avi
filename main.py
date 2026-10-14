"""
main.py -- Zerodha OptionSelling Engine | Brick 7
=================================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 7)
Date     : June 2026

Background Loop Process:
  - Enforces IP Guard whitelisting on startup and before each execution cycle.
  - Automates daily Zerodha login check/login via Password + TOTP on startup/expiry.
  - Runs periodic LTP polling and P&L updates (calc_portfolio_pnl) during market hours.
  - Monitors and auto-expires blocks (check_expiries).
  - Sends scheduled daily block summaries at market close.
  - Sends hourly heartbeats to Telegram/ntfy to indicate the engine is alive.
  - Responds dynamically to dashboard config controls (e.g. algo_running toggle).
  - Provides a dry-run/single-execution mode via `--once` command-line flag for testing.
"""

import sys
import time
from datetime import datetime
import pytz
import requests

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg
import utils
from kite_executor import kite_executor
import block_manager as bm
import pnl_engine as pe
import telegram_bot as tg
import equity_200dma_engine as eq_engine

IST = pytz.timezone("Asia/Kolkata")


def check_ip_guard() -> bool:
    """
    Enforces IP Whitelisting. Returns True if IP is correct or in paper mode.
    PERMANENT RULE: Whitelisted IP = 46.224.133.16
    """
    # Paper mode bypass removed

    allowed_ip = db.get("ALLOWED_TRADING_IP", "5.75.250.104").strip()

    # ANY = disable IP guard (for dynamic home broadband testing/override)
    if allowed_ip.upper() == "ANY":
        return True

    try:
        current_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        allowed_list = [ip.strip() for ip in allowed_ip.split(",")]
        if current_ip not in allowed_list:
            utils.log(f"IP GUARD TRIGGERED: Current IP {current_ip} not in whitelist {allowed_ip}", "ALERT")
            # Limit warning message to once per hour using db flag
            last_alert = db.get("last_ip_alert_time", "0")
            now_ts = time.time()
            if now_ts - float(last_alert) > 3600:
                tg.alert_ip_guard_violation(current_ip, allowed_ip)
                db.set("last_ip_alert_time", str(now_ts))
            return False
        return True
    except Exception as e:
        utils.log(f"Failed to check public IP: {e}. Skipping IP guard check.", "WARN")
        return True


def run_monday_rollover_check() -> None:
    """
    Monday weekly hedge rollover check (stub logic for block-based system).
    In v1.01 Base Model, active blocks and their hedges share the block's expiry.
    If weekly contracts are created, they would run in a weekly block, where both sell
    and hedge expire on the same day, so no mismatched rollover is required.
    We log this to console on Mondays past 14:00 IST for complete audit compliance.
    """
    now = datetime.now(IST)
    if now.weekday() == 0 and now.strftime("%H:%M") >= cfg.ROLLOVER_TIME:
        last_rollover = db.get("last_monday_rollover_check", "")
        today_str = now.strftime("%Y-%m-%d")
        if last_rollover != today_str:
            utils.log("Monday rollover check: All active block hedges use block expiry. Monthly blocks do not require weekly rollover.", "ROLLOVER")
            db.set("last_monday_rollover_check", today_str)


import os

def acquire_single_instance_lock():
    """Ensure only ONE instance of the engine runs at a time (Linux/VPS PID lock)."""
    try:
        import fcntl
        lock_file_path = "/tmp/zerodha_engine.pid"
        fp = open(lock_file_path, "w")
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except ImportError:
        return None
    except (IOError, OSError):
        print(f"[FATAL] Another instance of zerodha_engine (main.py) is already running! Exiting immediately.")
        sys.exit(1)


def start_engine_loop() -> None:
    """Main execution loop."""
    _pid_lock = acquire_single_instance_lock()
    utils.log("Starting Zerodha Option Selling trading engine background loop...", "INIT")

    # Force check_interval to 30 seconds in database
    db.set("check_interval", "30")

    # Command-line options
    once_mode = "--once" in sys.argv

    # 1. IP Whitelist check on startup
    if not check_ip_guard():
        utils.log("Startup IP Whitelist check failed. Engine is waiting for whitelisted IP connection.", "WARN")
        if once_mode:
            sys.exit(1)

    # 2. Login to Zerodha
    utils.log("Attempting initial login to Zerodha Kite Connect API...", "INIT")
    if kite_executor.login():
        tg.alert_login_success()
        tg.alert_engine_started()
    else:
        tg.alert_login_failed("Initial login failed. Check Password and TOTP key.")
        utils.log("Zerodha client login failed on startup. Engine will retry dynamically.", "WARN")
        if once_mode:
            sys.exit(1)

    # Track iteration times
    last_pnl_cycle_time = 0.0
    last_heartbeat_time = 0.0
    last_expiry_check_time = 0.0

    while True:
        try:
            # Dynamically reload secrets.txt in case operator updated credentials via dashboard
            db.load_secrets()

            # A. Check if algo is running (OFF toggle in dashboard)
            algo_running = db.get("algo_running", "ON") == "ON"
            if not algo_running:
                # Log only once in a while to prevent log spam
                if int(time.time()) % 60 < 10:
                    utils.log("Trading engine is currently PAUSED (algo_running = OFF).", "STATUS")
                if once_mode:
                    break
                time.sleep(10)
                continue

            # B. Check IP Guard
            if not check_ip_guard():
                if once_mode:
                    sys.exit(1)
                time.sleep(10)
                continue

            # C. Check login token freshness
            if True:
                if not kite_executor.ensure_logged_in():
                    utils.log("Zerodha session login is inactive or failed. Will retry later.", "AUTH")
                    tg.alert_login_failed("Trading engine dynamic login failed.")
                    time.sleep(300)
                    continue

            now = datetime.now(IST)
            now_time_str = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")

            # ── MARKET TRADING DAY FIREWALL (BRICK 1) ──
            if not utils.is_trading_day(now) and not once_mode:
                if int(time.time()) % 1800 < 15:
                    reason = "WEEKEND (Saturday/Sunday)" if now.weekday() >= 5 else f"NSE TRADING HOLIDAY ({today_str})"
                    utils.log(f"Market is CLOSED today: {reason}. All trading engines, pulses, and watchdogs are peacefully SLEEPING.", "MARKET_CLOSED")
                time.sleep(30)
                continue

            # Daily Strike Reset Check (Runs after 09:00 IST once per calendar day)
            if now_time_str >= "09:00":
                last_reset_date = db.get("last_daily_strike_reset_date", "")
                if last_reset_date != today_str:
                    utils.log("Running daily strike reset for closed strikes...", "INIT")
                    reset_count = bm.run_daily_strike_reset()
                    if reset_count > 0:
                        tg.send(f"🔄 <b>DAILY STRIKE RESET COMPLETE</b>\nReset {reset_count} closed strike(s) from previous days back to PENDING.")
                    db.set("last_daily_strike_reset_date", today_str)

            # Daily OS Option Anchor Refresh (Runs after 09:00 IST once per calendar day)
            if now_time_str >= "09:00":
                last_os_refresh_date = db.get("last_os_anchor_refresh_date", "")
                if last_os_refresh_date != today_str:
                    utils.log("Running daily OS strike anchor refresh from NSE previous close...", "INIT")
                    try:
                        import os_engine
                        refreshed_count = os_engine.refresh_all_os_anchors()
                        utils.log(f"Daily OS strike anchor refresh complete: {refreshed_count} contract(s) refreshed.", "INIT")
                    except Exception as e:
                        utils.log(f"Error in daily OS strike anchor refresh: {e}", "ERROR")
                    db.set("last_os_anchor_refresh_date", today_str)

            # Master Nifty Anchor is strictly manual (No automated 09:15 overwrite)

            # Automated Equity 200 DMA Scans (Runs twice daily at 10:00 AM & 14:00 PM IST)
            if now_time_str >= "10:00":
                last_m_scan = db.get("last_equity_morning_scan_date", "")
                if last_m_scan != today_str:
                    utils.log("Running automated 10:00 AM Equity 200 DMA scan...", "EQUITY")
                    try:
                        eq_engine.run_scheduled_equity_scan("10:00 AM Morning Scan")
                    except Exception as e:
                        utils.log(f"Error in 10:00 AM Equity scan: {e}", "ERROR")
                    db.set("last_equity_morning_scan_date", today_str)

            if now_time_str >= "14:00":
                last_a_scan = db.get("last_equity_afternoon_scan_date", "")
                if last_a_scan != today_str:
                    utils.log("Running automated 2:00 PM (14:00) Equity 200 DMA scan...", "EQUITY")
                    try:
                        eq_engine.run_scheduled_equity_scan("2:00 PM Afternoon Scan")
                    except Exception as e:
                        utils.log(f"Error in 2:00 PM Equity scan: {e}", "ERROR")
                    db.set("last_equity_afternoon_scan_date", today_str)

            # D. Expiry Monitor (check every 10 minutes)
            if time.time() - last_expiry_check_time >= 600 or once_mode:
                utils.log("Running block expiry checks...", "EXPIRY")
                expired_block_ids = bm.check_expiries()
                for bid in expired_block_ids:
                    # Retrieve block info from historical/archived view
                    block = db.get_block(bid)
                    if block:
                        tg.alert_block_expired(block["block_number"], block["expiry_date"])
                last_expiry_check_time = time.time()

            # E. Monday Rollover check
            run_monday_rollover_check()

            # E1. 14:57 IST Master Anchor Continuation Decision for M-Units (V5.0)
            anchor_decision_time = getattr(cfg, "MASTER_DECISION_TIME", "14:57")
            trading_cutoff = getattr(cfg, "ACTIVE_TRADING_CUTOFF_TIME", "15:13")
            if (anchor_decision_time <= now_time_str < trading_cutoff):
                last_3pm_decision_date = db.get("last_3pm_decision_date", "")
                if last_3pm_decision_date != today_str:
                    utils.log(f"⏰ {anchor_decision_time} IST Watchdog: Running Master Anchor Continuation Decision for M-Units (14:57 - 15:00 window)...", "DECISION")
                    bm.execute_3pm_master_anchor_decision()
                    db.set("last_3pm_decision_date", today_str)

            # E1-b. 15:01 IST OS Option Selling Line Audit & Momentum Decision (OS1, OS2, OS3)
            os_decision_time = getattr(cfg, "OS_DECISION_TIME", "15:01")
            if (os_decision_time <= now_time_str < trading_cutoff):
                last_os_3pm_date = db.get("last_os_3pm_decision_date", "")
                if last_os_3pm_date != today_str:
                    utils.log(f"⏰ {os_decision_time} IST Watchdog: Running OS Option Selling Line Audit across OS-Units (15:01 - 15:04 window)...", "DECISION")
                    try:
                        import os_engine
                        os_engine.evaluate_os_3pm_decision()
                        db.set("last_os_3pm_decision_date", today_str)
                    except Exception as os_err:
                        utils.log(f"Error in OS {os_decision_time} decision: {os_err}", "ERROR")

            # E1-c. Weekly ST 2-Hour Autonomous Engine Pulse Watchdog (11:15, 13:15, 15:10)
            try:
                import weekly_st_engine as wst_engine
                in_w_pulse, w_pulse_desc = wst_engine.is_pulse_time()
                if in_w_pulse:
                    # Assign canonical Pulse ID to prevent minute-by-minute repeated triggers
                    if "11:15" in w_pulse_desc:
                        pulse_id = "PULSE_11_15"
                    elif "01:15" in w_pulse_desc:
                        pulse_id = "PULSE_13_15"
                    elif "03:10" in w_pulse_desc:
                        pulse_id = "PULSE_15_10"
                    else:
                        pulse_id = f"PULSE_{now_time_str[:5]}"
                    
                    last_w_pulse_key = f"last_w_pulse_{pulse_id}"
                    if db.get(last_w_pulse_key, "") != today_str:
                        # Lock pulse key BEFORE evaluation to eliminate race conditions
                        db.set(last_w_pulse_key, today_str)
                        pulse_res = wst_engine.evaluate_weekly_st_pulse(force_pulse=False)
                        if pulse_res:
                            utils.log(f"Weekly ST Pulse result: {pulse_res.get('message', '')}", "W_PULSE")
            except Exception as w_err:
                utils.log(f"Error in Weekly ST-2H Pulse watchdog: {w_err}", "ERROR")

            # E2. 15:13 IST EOD Orphan Hedge Watchdog Protocol (V5.1)
            orphan_sweep_time = getattr(cfg, "ORPHAN_SWEEP_START", "15:13")
            if (orphan_sweep_time <= now_time_str <= cfg.MARKET_END_TIME):
                last_sweep_date = db.get("last_eod_hedge_sweep_date", "")
                if last_sweep_date != today_str:
                    utils.log(f"🧹 {orphan_sweep_time} IST Watchdog: Running EOD Orphan Hedge Sweep with Broker Ground Truth...", "SWEEP")
                    try:
                        res_swp = bm.sweep_orphan_hedges_now()
                        db.set("last_eod_hedge_sweep_date", today_str)
                    except Exception as ex_swp:
                        utils.log(f"EOD Orphan Hedge Sweep error in main loop: {ex_swp}", "WARN")

            # Process pending closes (Runs every loop iteration / 10s)
            bm.process_pending_closes()

            # F. Daily Summary EOD Check (Runs at market end: 15:45 IST)
            if now_time_str >= cfg.MARKET_END_TIME and now_time_str < "16:45" or once_mode:
                last_summary_date = db.get("last_daily_summary_date", "")
                if last_summary_date != today_str:
                    utils.log("Market closed. Sending daily block and portfolio summaries...", "SUMMARY")
                    portfolio = pe.calc_portfolio_pnl()
                    tg.send_all_block_summaries(portfolio)
                    db.set("last_daily_summary_date", today_str)

            # G. Periodic Heartbeat (every 15 minutes / 900s)
            if time.time() - last_heartbeat_time >= 900 or once_mode:
                portfolio = pe.calc_portfolio_pnl()
                utils.log("Sending periodic system heartbeat...", "HEARTBEAT")
                tg.alert_heartbeat(portfolio)
                last_heartbeat_time = time.time()

            # H. P&L Cycle (runs during market hours: 09:15 - 15:30 IST on trading days)
            is_market_open = utils.is_market_hours()
            check_interval = int(db.get("check_interval", str(cfg.DEFAULT_CHECK_INTERVAL)))

            if is_market_open or once_mode:
                if time.time() - last_pnl_cycle_time >= check_interval or once_mode:
                    utils.log(f"Running P&L update cycle (Interval: {check_interval}s)...", "CYCLE")
                    pe.run_pnl_cycle()
                    last_pnl_cycle_time = time.time()

            if once_mode:
                utils.log("Dry run / --once execution complete. Exiting.", "INFO")
                break

            # Sleep 10s between checks to allow responsive toggles
            time.sleep(10)

        except KeyboardInterrupt:
            utils.log("Engine execution terminated by user (Ctrl+C).", "INFO")
            tg.alert_engine_stopped("Manual stop via KeyboardInterrupt")
            break
        except Exception as e:
            utils.log(f"Critical error in engine loop: {e}", "ERROR")
            tg.send(f"⚠️ <b>CRITICAL MAIN ERROR</b>\nEngine encountered error: <code>{e}</code>", alert_key="critical_main_err", cooldown_sec=300)
            if once_mode:
                sys.exit(1)
            time.sleep(15)


if __name__ == "__main__":
    start_engine_loop()
