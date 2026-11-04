import paramiko
sys_secrets = {}
with open(r'c:\Users\Dell\Desktop\cheenna zerodha\secrets.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            sys_secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(sys_secrets['VPS_IP'], username=sys_secrets['VPS_USER'], password=sys_secrets['VPS_PASSWORD'])
cmd = 'systemctl is-active zerodha_engine.service zerodha_dashboard.service && curl -s -o /dev/null -w "HTTP: %{http_code}\\n" http://127.0.0.1:9007/'
stdin, stdout, stderr = client.exec_command(cmd)
print("VPS Status:\n" + stdout.read().decode())
client.close()

