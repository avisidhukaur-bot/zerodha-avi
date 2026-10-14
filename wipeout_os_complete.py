import paramiko
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

print("="*60)
print("1. WIPING OUT OS TRADE & UNLOCKING DRAFT ON LOCAL DB")
print("="*60)
import db
db.wipeout_os_pod("OS1")
db.unlock_os_settings()
db.reset_os_daily_trade_flag("OS1")

# Clear all os_locked settings
conn = db._conn()
cur = conn.cursor()
cur.execute("DELETE FROM settings WHERE key LIKE 'os_locked_%'")
cur.execute("DELETE FROM settings WHERE key LIKE 'os_traded_date_%'")
cur.execute("DELETE FROM settings WHERE key = 'os_settings_locked'")
cur.execute("DELETE FROM blocks WHERE UPPER(anchor_unit_name) LIKE 'OS%'")
conn.commit()
conn.close()
print("✅ Local DB cleared of OS trade and locked settings.")

print("\n" + "="*60)
print("2. WIPING OUT OS TRADE & UNLOCKING DRAFT ON VPS DB")
print("="*60)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

vps_script = """import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import sqlite3

db.wipeout_os_pod('OS1')
db.unlock_os_settings()
db.reset_os_daily_trade_flag('OS1')

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
cur.execute("DELETE FROM settings WHERE key LIKE 'os_locked_%'")
cur.execute("DELETE FROM settings WHERE key LIKE 'os_traded_date_%'")
cur.execute("DELETE FROM settings WHERE key = 'os_settings_locked'")
cur.execute("DELETE FROM blocks WHERE UPPER(anchor_unit_name) LIKE 'OS%'")
conn.commit()
conn.close()
print("✅ VPS DB cleared of all OS locked parameters and reset to clean Draft Mode.")
"""

sftp = client.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/clear_os.py', 'w') as f:
    f.write(vps_script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/clear_os.py')
print(stdout.read().decode())
print(stderr.read().decode())

print("Restarting zerodha_dashboard.service on VPS to clear UI session state...")
stdin, stdout, stderr = client.exec_command('systemctl restart zerodha_dashboard.service')
print("✅ Dashboard restarted cleanly.")

client.close()
print("="*60)
print("OS PURGE & RESET COMPLETE!")
print("="*60)
