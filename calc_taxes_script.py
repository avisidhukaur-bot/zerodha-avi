import paramiko, os

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'])

calc_script = '''from kite_executor import kite_executor

kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()

trades = kite_executor.kite.trades()
morning_syms = ["NIFTY26SEP24300CE", "NIFTY26SEP24800CE", "NIFTY26SEP24400CE"]

morning_trades = [t for t in trades if t.get("tradingsymbol") in morning_syms]

def calculate_charges(trade_list):
    total_buy_val = 0.0
    total_sell_val = 0.0
    order_ids = set()
    
    for t in trade_list:
        val = float(t["quantity"]) * float(t["average_price"])
        order_ids.add(t["order_id"])
        if t["transaction_type"] == "BUY":
            total_buy_val += val
        else:
            total_sell_val += val
            
    orders_count = len(order_ids)
    brokerage = orders_count * 20.0
    stt = total_sell_val * 0.001  # STT 0.1% on sell premium
    exchange_txn = (total_buy_val + total_sell_val) * 0.00035
    sebi_charges = (total_buy_val + total_sell_val) * 0.000001
    gst = (brokerage + exchange_txn + sebi_charges) * 0.18
    stamp_duty = total_buy_val * 0.00003
    
    total_taxes_charges = brokerage + stt + exchange_txn + gst + stamp_duty + sebi_charges
    gross_pnl = total_sell_val - total_buy_val
    net_pnl = gross_pnl - total_taxes_charges
    
    return {
        "orders_count": orders_count,
        "trades_count": len(trade_list),
        "total_buy_val": total_buy_val,
        "total_sell_val": total_sell_val,
        "gross_pnl": gross_pnl,
        "brokerage": brokerage,
        "stt": stt,
        "exchange_txn": exchange_txn,
        "gst": gst,
        "stamp_duty": stamp_duty,
        "total_taxes_charges": total_taxes_charges,
        "net_pnl": net_pnl
    }

print("=== MORNING TRADES CHARGES & PNL (24300 / 24800 / 24400) ===")
res_morning = calculate_charges(morning_trades)
for k, v in res_morning.items():
    print(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}")
'''

sftp = client.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/calc_tax.py', 'w') as f:
    f.write(calc_script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/calc_tax.py')
out = stdout.read().decode()
err = stderr.read().decode()
print("OUTPUT:\n", out)
if err:
    print("ERROR:\n", err)

client.close()
