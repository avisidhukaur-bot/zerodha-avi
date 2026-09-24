import sqlite3

conn = sqlite3.connect('zerodha_trader.db')
cur = conn.cursor()
cur.execute('UPDATE blocks SET master_anchor_price = 23225.0 WHERE anchor_unit_name = "M1" OR block_id = 56')
conn.commit()
print("Updated rows:", cur.rowcount)
cur.execute('SELECT block_id, anchor_unit_name, master_anchor_price FROM blocks')
for r in cur.fetchall():
    print("Block:", r)
conn.close()
