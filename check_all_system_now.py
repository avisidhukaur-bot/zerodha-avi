import sys
import os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paramiko

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

print("="*60)
print("1. CHECKING VPS HEALTH & SERVICES (5.75.250.104)")
print("="*60)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
    print("VPS Connection: ONLINE (HostAsia VPS 5.75.250.104)")
    
    def run(cmd):
        _, out, err = c.exec_command(cmd)
        return out.read().decode(errors='replace').strip()

    print("• VPS Engine Status:")
    services = ["zerodha_engine.service", "zerodha_dashboard.service", "zerodha_commodity.service"]
    for s in services:
        st = run(f"systemctl is-active {s}")
        print(f"   - {s}: {st.upper()}")
        
    print("\n• VPS Dashboard Port (9007):")
    print("  ", run("ss -tlnp | grep 9007"))
    
    print("\n• VPS Engine Log (Latest):")
    print(run("tail -n 15 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log"))
    
    c.close()
except Exception as e:
    print("VPS Error:", e)

print("\n" + "="*60)
print("2. CHECKING ZERODHA AUTHENTICATION & LOGIN")
print("="*60)
try:
    import db
    from kite_executor import kite_executor
    db.load_secrets()
    print("Attempting Zerodha Kite Login via TOTP...")
    login_success = kite_executor.ensure_logged_in()
    if login_success:
        print("✅ Zerodha Kite Login: SUCCESS!")
        prof = kite_executor.kite.profile()
        print(f"• User ID: {prof.get('user_id')} ({prof.get('user_name')})")
        m = kite_executor.kite.margins('equity')
        print(f"• Available Cash: Rs {m.get('available', {}).get('cash', 0):,.2f}")
        print(f"• Net Margin: Rs {m.get('net', 0):,.2f}")
        pos = kite_executor.kite.positions()
        net = [p for p in pos.get('net', []) if p.get('quantity') != 0]
        print(f"• Open Positions: {len(net)}")
        for p in net:
            print(f"   - {p.get('tradingsymbol')} Qty: {p.get('quantity')} PnL: Rs {p.get('pnl')}")
    else:
        print("❌ Zerodha Kite Login Failed! Checking reason...")
except Exception as e:
    print("Zerodha error:", e)

print("\n" + "="*60)
print("3. CHECKING GIT STATUS")
print("="*60)
import subprocess
try:
    res = subprocess.run(["git", "status", "-s"], capture_output=True, text=True)
    res_branch = subprocess.run(["git", "branch", "-vv"], capture_output=True, text=True)
    print("• Branch info:\n", res_branch.stdout.strip())
    modified_count = len([l for l in res.stdout.splitlines() if l.strip()])
    print(f"• Uncommitted changes / files: {modified_count}")
except Exception as e:
    print("Git error:", e)

print("="*60)
