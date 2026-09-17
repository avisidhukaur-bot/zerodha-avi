import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

remote_lines = [
    "import os, sys",
    "sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "import db",
    "import kite_executor",
    "import pnl_engine as pe",
    "",
    "print('=== ALL BLOCKS & STRIKES ===')",
    "blocks = db.get_all_blocks()",
    "for b in blocks:",
    "    b_id = b['block_id']",
    "    print(f\"\\n>>> Block ID: {b_id} | Name: {b.get('anchor_unit_name')} | Side: {b.get('side_type')} | Status: {b.get('status')} | Anchor: {b.get('master_anchor_price')} | Expiry: {b.get('expiry_date')}\")",
    "    strikes = db.get_strikes_by_block(b_id)",
    "    for s in strikes:",
    "        ltp = pe.fetch_ltp(s, force_refresh=True)",
    "        print(f\"   Strike ID: {s['strike_id']} | Type: {s['option_type']} {s['leg_type']} | Strike: {s['strike_price']} | Symbol: {s.get('trading_symbol')} | Anchor: {s.get('anchor_price')} | LTP: {ltp} | SL: {s.get('stop_loss')} | Status: {s.get('status')}\")",
    "",
    "print('\\n=== LIVE BROKER POSITIONS ===')",
    "try:",
    "    net_pos = kite_executor.get_positions().get('net', [])",
    "    for p in net_pos:",
    "        if p.get('quantity') != 0:",
    "            print(f\"Symbol: {p['tradingsymbol']} | Qty: {p['quantity']} | Buy: {p.get('buy_price')} | Sell: {p.get('sell_price')} | PnL: {p.get('pnl')} | LTP: {p.get('last_price')}\")",
    "except Exception as e:",
    "    print('Broker positions fetch error:', e)",
    "",
    "print('\\n=== SYSTEM SETTINGS ===')",
    "for k in ['algo_running', 'paper_mode', 'lot_size', 'buffer_tolerance', 'continuous_hold_min', 'master_nifty_anchor']:",
    "    print(f\"{k}: {db.get(k)}\")"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/os1_check.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/os1_check.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
