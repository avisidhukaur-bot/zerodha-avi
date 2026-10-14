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
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = '''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db, pnl_engine as pe
portfolio = pe.calc_portfolio_pnl(pe.fetch_all_ltps())
print("Total PnL:", portfolio.get("total_pnl"))
print("Active Blocks:", portfolio.get("active_blocks"))
for bp in portfolio.get("block_pnls", []):
    b = bp["block"]
    print(f"Block #{b.get('block_number')} | Unit {b.get('anchor_unit_name')} | Status: {b.get('status')} | Total PnL: Rs {bp.get('total_pnl'):,.2f}")
    for sp in bp.get("strike_pnls", []):
        print(f"   {sp['strike_price']} {sp['option_type']} {sp['leg_type']} | Status: {sp['status']} | LTP: {sp['ltp']} | PnL: Rs {sp['pnl']:,.2f}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_verify_dashboard.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_verify_dashboard.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.exec_command('rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_verify_dashboard.py')
c.close()
