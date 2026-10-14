import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=10)

remote_lines = [
    "import os, sys",
    "sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "from kite_executor import kite_executor",
    "import db",
    "kite_executor.ensure_logged_in()",
    "k = kite_executor.kite",
    "",
    "print('=== NIFTY SPOT PRICE ===')",
    "try:",
    "    spot_q = k.quote(['NSE:NIFTY 50'])",
    "    spot = spot_q.get('NSE:NIFTY 50', {}).get('last_price', 0)",
    "    print(f'NIFTY 50 Spot: {spot}')",
    "except Exception as e:",
    "    print('Spot quote error:', e)",
    "",
    "print('\\n=== LIVE BROKER POSITIONS ===')",
    "try:",
    "    pos = k.positions().get('net', [])",
    "    for p in pos:",
    "        if p.get('quantity') != 0:",
    "            sym = p.get('tradingsymbol')",
    "            qty = p.get('quantity')",
    "            buy = p.get('buy_price')",
    "            sell = p.get('sell_price')",
    "            ltp = p.get('last_price')",
    "            pnl = p.get('pnl')",
    "            m2m = p.get('m2m')",
    "            print(f\"{sym} | Qty: {qty} | BuyPrice: {buy} | SellPrice: {sell} | LTP: {ltp} | PnL: ₹{pnl:,.2f} | M2M: ₹{m2m:,.2f}\")",
    "except Exception as e:",
    "    print('Pos error:', e)",
    "",
    "print('\\n=== ACTIVE BLOCKS & STRIKES IN DB ===')",
    "try:",
    "    blocks = db.get_active_blocks()",
    "    for b in blocks:",
    "        print(f\"Block #{b['block_id']} ({b.get('anchor_unit_name')}): Regime={b.get('current_regime')} | MasterAnchor={b.get('master_anchor_price')}\")",
    "        strikes = db.get_strikes_for_block(b['block_id'])",
    "        for s in strikes:",
    "            print(f\"  -> Strike {s.get('strike_price')} {s.get('option_type')} | Leg: {s.get('leg_type')} | State: {s.get('trade_state')} | Status: {s.get('status')}\")",
    "except Exception as e:",
    "    print('DB query error:', e)"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/check_live_mkt_and_pos.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/check_live_mkt_and_pos.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
