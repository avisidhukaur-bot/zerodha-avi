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

IST = pytz.timezone("Asia/Kolkata")


def check_ip_guard() -> bool:
    """
    Enforces IP Whitelisting. Returns True if IP is correct or in paper mode.
    PERMANENT RULE: Whitelisted IP = 46.224.133.16
    """
    # Paper mode bypass removed

    allowed_ip = db.get("ALLOWED_TRADING_IP", "46.224.133.16").strip()

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


def start_engine_loop() -> None:
    """Main execution loop."""
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

            # Daily Strike Reset Check (Runs after 09:00 IST once per calendar day)
            if now_time_str >= "09:00":
                last_reset_date = db.get("last_daily_strike_reset_date", "")
                if last_reset_date != today_str:
                    utils.log("Running daily strike reset for closed strikes...", "INIT")
                    reset_count = bm.run_daily_strike_reset()
                    if reset_count > 0:
                        tg.send(f"🔄 <b>DAILY STRIKE RESET COMPLETE</b>\nReset {reset_count} closed strike(s) from previous days back to PENDING.")
                    db.set("last_daily_strike_reset_date", today_str)

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

            # Process pending closes (Runs every loop iteration / 10s)
            bm.process_pending_closes()

            # F. Daily Summary EOD Check (Runs at market end: 15:30 IST)
            if now_time_str >= cfg.MARKET_END_TIME and now_time_str < "16:30" or once_mode:
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

            # H. P&L Cycle (runs during market hours: 09:15 - 15:30 IST)
            is_market_open = (cfg.MARKET_START_TIME <= now_time_str <= cfg.MARKET_END_TIME)
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
