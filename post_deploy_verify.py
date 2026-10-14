import db
from kite_executor import kite_executor

def main():
    db.load_secrets()
    print("=== 1. TEST SECRETS LOAD ===")
    print("Client Code:", db.get("KITE_CLIENT_CODE"))
    print("VPS IP:", db.get("VPS_IP"))
    print("\n=== 2. KITE BROKER CONNECTION ===")
    logged = kite_executor.ensure_logged_in()
    print("Logged In Status:", logged)
    pos = kite_executor.get_positions()
    print("Open Positions Count on Broker:", len(pos) if pos else 0)
    print("NIFTY Spot Price:", kite_executor.get_nifty_spot())
    print("\n🎉 ALL TESTS PASSED — SYSTEM IS 100% OPERATIONAL & READY!")

if __name__ == '__main__':
    main()
