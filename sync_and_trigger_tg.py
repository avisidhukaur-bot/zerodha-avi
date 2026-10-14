import paramiko
import sys
from datetime import datetime
import pytz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

sync_script = f"""
import sqlite3
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import telegram_bot as tg
import pnl_engine as pe
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()

# 1. Update strikes 154 and 155 to OPEN
cur.execute("UPDATE strikes SET status='OPEN', trade_state='OPEN' WHERE strike_id IN (154, 155)")

# 2. Check if legs exist for 154 and 155
cur.execute("SELECT leg_id, strike_id FROM legs WHERE strike_id=154 AND (exit_time IS NULL OR exit_time='')")
if not cur.fetchone():
    cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (154, 42.40, '{now_str}', '2106720737909033984')")
    print("Inserted Open Leg for Strike 154 (Hedge)")

cur.execute("SELECT leg_id, strike_id FROM legs WHERE strike_id=155 AND (exit_time IS NULL OR exit_time='')")
if not cur.fetchone():
    cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (155, 147.10, '{now_str}', '2106720743143525376')")
    print("Inserted Open Leg for Strike 155 (Sell)")

conn.commit()
conn.close()

# 3. Calculate PnL and send Telegram Heartbeat
print("=== CALCULATING LIVE PNL & SENDING TELEGRAM UPDATE ===")
pnl_data = pe.calc_portfolio_pnl()
print("Total Portfolio PnL:", pnl_data.get('total_pnl'))
print("Open Strikes Count:", pnl_data.get('open_strikes'))

tg.alert_heartbeat_live(pnl_data)
print("Telegram Alert Sent!")
"""

sftp = c.open_sftp()
with sftp.file('/tmp/sync_db_and_tg.py', 'w') as f:
    f.write(sync_script)
sftp.close()

_, stdout, stderr = c.exec_command("/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 /tmp/sync_db_and_tg.py && systemctl restart zerodha_engine.service zerodha_dashboard.service")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

# Sync DB to local
sftp = c.open_sftp()
sftp.get("/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db", "zerodha_trader.db")
sftp.close()

c.close()
print("Sync to VPS and Local completed!")
