import paramiko
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connected = False
for i in range(5):
    try:
        print(f"Connecting to VPS attempt {i+1}...")
        c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
        connected = True
        print("Connected!")
        break
    except Exception as e:
        print("Attempt failed:", e)
        time.sleep(1)

if not connected:
    sys.exit(1)

nginx_conf = """server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    location / {
        proxy_pass http://127.0.0.1:9007/;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://127.0.0.1:9007/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
"""

sftp = c.open_sftp()
with sftp.file("/etc/nginx/sites-available/default", "w") as f:
    f.write(nginx_conf)
sftp.close()

def run(cmd):
    print(f"\n=== CMD: {cmd} ===")
    _, out, err = c.exec_command(cmd)
    o = out.read().decode('utf-8', errors='replace')
    e = err.read().decode('utf-8', errors='replace')
    if o:
        print(o.strip())
    if e:
        print("ERR:", e.strip())

run("nginx -t")
run("systemctl restart nginx")
run("systemctl status nginx --no-pager")

c.close()
print("Nginx proxy setup completed successfully!")
