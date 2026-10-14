import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if any(k in line.lower() for k in ['trade_state', 'st.dataframe', 'calc_block_pnl', 'get_strikes_by_block', 'render_v5', 'unified_card', 'st.metric']):
        print(f"{i+1}: {line.strip()[:120]}")
