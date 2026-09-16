import sqlite3

conn = sqlite3.connect('zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== LOCAL DB ACTIVE BLOCKS ===")
blocks = cur.execute('SELECT * FROM blocks WHERE status="ACTIVE"').fetchall()
for b in blocks:
    print(dict(b))

print("\n=== LOCAL DB ALL STRIKES ===")
strikes = cur.execute('SELECT * FROM strikes').fetchall()
for s in strikes:
    print(dict(s))

print("\n=== LOCAL DB ALL LEGS ===")
legs = cur.execute('SELECT * FROM legs').fetchall()
for l in legs:
    print(dict(l))
