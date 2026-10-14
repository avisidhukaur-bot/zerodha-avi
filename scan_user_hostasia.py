import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

folders = [
    r"c:\Users\Dell\Desktop",
    r"c:\Users\Dell\Downloads",
    r"c:\Users\Dell\Documents"
]

keywords = ['hostasia', 'host-asia', 'host asia', 'hetzner', 'your-server.de', '5.75.250.104', 'iAvmEHjPxmJW', 'U4CJs4HKbMMJ', 'hostinger']

found = []
for folder in folders:
    if not os.path.exists(folder):
        continue
    for root, dirs, files in os.walk(folder):
        if any(x in root for x in ['.git', 'node_modules', '__pycache__', 'venv']):
            continue
        for f in files:
            if f.endswith(('.txt', '.md', '.json', '.html', '.pdf', '.docx', '.csv', '.py', '.log', '.bat')):
                p = os.path.join(root, f)
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                        txt = fp.read()
                        for kw in keywords:
                            if kw.lower() in txt.lower():
                                found.append((p, kw))
                                break
                except Exception:
                    pass

print(f"Total files matching keywords: {len(found)}")
for p, kw in found:
    print(f"[{kw}] -> {p}")
