import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import time
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()

blocks = db.get_all_blocks(status_filter="ACTIVE")
m2_block = next((b for b in blocks if (b.get("anchor_unit_name") or "").upper() == "M2"), None)
if m2_block:
    bid = m2_block["block_id"]
    strikes = db.get_strikes_by_block(bid)
    has_pe_sell = any(s["strike_price"] == 22600 and s["option_type"] == "PE" for s in strikes)
    if not has_pe_sell:
        p_s_id = db.add_strike(
            block_id=bid,
            strike_price=22600,
            option_type="PE",
            leg_type="SELL",
            anchor_price=100.0,
            lots=4,
            expiry_date="27-Oct-2026",
            sl_pct=25.0,
            sl_price=125.0,
            reentry_enabled=1,
            trade_state="PENDING"
        )
        db.update_strike_status(p_s_id, "PENDING")
        p_h = next((s for s in strikes if s["strike_price"] == 22100 and s["option_type"] == "PE"), None)
        if p_h:
            p_h_id = p_h["strike_id"]
            conn = db._conn()
            conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (p_s_id, p_h_id))
            conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (p_h_id, p_s_id))
            conn.commit()
            conn.close()
        print(f"Added pending PE SELL 22600 strike {p_s_id}")

# Restart dashboard
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/add_pe_wing.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/add_pe_wing.py && systemctl restart zerodha_dashboard && systemctl restart zerodha_engine")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)

c.close()
