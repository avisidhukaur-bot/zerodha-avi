from kite_executor import kite_executor

if kite_executor.login():
    orders = kite_executor.get_all_orders()
    print("Total orders found:", len(orders))
    for o in orders:
        if str(o.get("status", "")).upper() == "REJECTED":
            print(f"Time: {o.get('order_timestamp')}")
            print(f"Symbol: {o.get('tradingsymbol')} | Qty: {o.get('quantity')} | Type: {o.get('transaction_type')}")
            print(f"Status Message / Reason: {o.get('status_message')}")
            print("-" * 50)
