import os
import re

search_terms = ['hostasia', 'hostinger', 'hetzner', 'server', 'console', 'billing', 'vps_password', 'root@', '5.75.250.104', 'host', 'cpanel']
base_dir = r"c:\Users\Dell\Desktop"

results = []

for root, dirs, files in os.walk(base_dir):
    # skip .git and node_modules
    if '.git' in root or 'node_modules' in root:
        continue
    for file in files:
        if file.endswith(('.txt', '.md', '.json', '.js', '.py', '.html', '.bat', '.env', '.log')):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for term in search_terms:
                        if re.search(r'\b' + re.escape(term) + r'\b', content, re.IGNORECASE):
                            # extract matching lines
                            lines = content.splitlines()
                            for idx, l in enumerate(lines):
                                if term.lower() in l.lower():
                                    results.append(f"{filepath} [Line {idx+1}]: {l.strip()}")
            except Exception as e:
                pass

print(f"Total Matches Found: {len(results)}\n")
for r in results[:40]:
    print(r)
