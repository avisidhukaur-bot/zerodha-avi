"""
morning_refresh.py — Automated Morning System Refresh for Zerodha OS
Runs automatically every morning at 08:50 AM IST (Monday to Friday)
"""
import sys
import os
from datetime import datetime
import pytz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import db
import utils
from kite_executor import kite_executor
import block_manager as bm
import telegram_bot as tg
import config as cfg

IST = pytz.timezone("Asia/Kolkata")

def run_morning_refresh():
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    now_str = now.strftime("%H:%M:%S")
    
    print(f"[{now_str}] 🌅 Starting Morning System Refresh...")
    utils.log("Starting automated morning system refresh...", "INIT")
    
    # 1. Load secrets & verify DB
    db.load_secrets()
    
    # 2. Fresh Zerodha TOTP Login & Token generation
    print("🔑 Step 1: Generating fresh Zerodha Kite session...")
    login_ok = kite_executor.ensure_logged_in()
    if login_ok:
        print("✅ Kite login successful and session verified.")
    else:
        print("⚠️ Kite login failed. Check TOTP / credentials.")
        tg.send("⚠️ <b>MORNING LOGIN FAILED</b>\nCould not authenticate Zerodha session.")
        return False
    
    kite = kite_executor.kite
    
    # 3. Refresh Daily Instruments Cache
    print("📥 Step 2: Refreshing daily instruments master cache...")
    try:
        if kite:
            instruments = kite.instruments("NFO")
            if instruments:
                import pandas as pd
                df = pd.DataFrame(instruments)
                cache_path = os.path.join(BASE_DIR, "zerodha_instruments.csv")
                df.to_csv(cache_path, index=False)
                print(f"✅ Cached {len(df)} NFO instruments locally.")
    except Exception as e:
        print("Instruments cache warning:", e)
    
    # 4. Run Daily Strike Reset (previous closed strikes back to PENDING)
    print("🔄 Step 3: Running daily strike reset for closed strikes...")
    reset_count = bm.run_daily_strike_reset()
    db.set("last_daily_strike_reset_date", today_str)
    print(f"✅ Reset {reset_count} closed strike(s) back to PENDING.")
    
    # 5. Clear all stale entry countdown timers
    print("⏱️ Step 4: Clearing all stale entry countdown timers...")
    import sqlite3
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    settings = conn.execute("SELECT key FROM settings WHERE key LIKE 'entry_trigger_time_%'").fetchall()
    for s in settings:
        db.set(s['key'], '0')
    conn.close()
    print("✅ All entry trigger timers reset to 0.")
    
    # 6. Ensure default 5-min rule & auto re-entry ON
    db.set('entry_delay_seconds', '300')
    db.set('buffer_tolerance', '2.0')
    db.set('auto_reentry_enabled', 'ON')
    db.set('max_same_day_reentries', '5')
    
    # 7. Fetch Spot and Available Margin
    spot = kite_executor.get_nifty_spot()
    available_cash = 0.0
    try:
        if kite:
            m = kite.margins('equity')
            available_cash = m.get('available', {}).get('cash', 0)
    except Exception as e:
        print(f"Margin fetch warning: {e}")
    
    print(f"💰 Available Margin: ₹{available_cash:,.2f}")
    print(f"📈 Nifty Live Spot: {spot:.2f}")
    
    # 8. Send Morning Ready Notification
    alert_msg = (
        f"🌅 <b>MORNING SYSTEM REFRESH COMPLETE</b> 🌅\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date: <b>{today_str}</b> | ⏰ Time: <b>{now_str} IST</b>\n"
        f"🔑 <b>Zerodha Session</b>: Logged in & Active ✅\n"
        f"💰 <b>Available Margin</b>: ₹{available_cash:,.2f}\n"
        f"📈 <b>Nifty 50 Spot</b>: {spot:.2f}\n"
        f"🔄 <b>Strikes Reset</b>: {reset_count} strike(s) reset to PENDING\n"
        f"⏱️ <b>Entry Delay Rule</b>: 5 Minutes Below Anchor (Active)\n"
        f"🤖 <b>Auto Re-Entry</b>: ON (5 Minutes / Max 5 per day)\n"
        f"🛑 <b>Stop-Loss Rule</b>: Anchor Price + ₹2.00 Buffer\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <b>System is 100% READY for 09:15 AM Market Open!</b>"
    )
    tg.send(alert_msg)
    print("✅ Morning Refresh Complete & Alert Sent!")
    return True

if __name__ == "__main__":
    run_morning_refresh()
