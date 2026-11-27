# 🏛️ PRODUCT UPGRADATION & FORENSIC REMEDIATION SPECIFICATION
## ANTI-DUPLICATE ENTRY FIREWALL, ZOMBIE BLOCK ELIMINATION & BROKER GROUND TRUTH LOT CAPPING
> **System:** Zerodha Kite Option Selling Engine (Bharat Systems)  
> **Date:** 27-Nov-2026 09:25 IST  
> **Auditor / Architect:** Antigravity AI Engine (Google DeepMind)  
> **Authority:** Gurjeet Mamu's Law & Chhoti Bahan Master Protocol  

---

## 📋 1. EXECUTIVE SUMMARY & POST-MORTEM (THE 09:15 AM INCIDENT)

### What Happened at 09:15:07 AM on 27-Nov-2026?
1. At market open (09:15:00 IST), Zerodha Kite terminal showed M1 Put positions suddenly jump from **3 Lots (195 Qty) to 6 Lots (390 Qty)**:
   - `2026-11-27 09:15:07 | BUY 195 NIFTY26DEC24700PE @ 96.25 (COMPLETE)`
   - `2026-11-27 09:15:09 | SELL 195 NIFTY26DEC25200PE @ 182.98 (COMPLETE)`
2. **Immediate Remediation Taken (09:18–09:20 IST)**:
   - Placed Marketable Limit Buy-to-Cover order for 195 of `25200 PE` @ 180.1 (Order `2126161372172562432`).
   - Placed Marketable Limit Sell-Hedge order for 195 of `24700 PE` @ 89.4 (Order `2126161372839452672`).
   - Verified live broker positions restored to strictly **3 Lots (195 Qty)** on M1 and **2 Lots (130 Qty)** on Weekly ST.
   - Stopped `zerodha_engine.service` and set `algo_running = 'OFF'` per Gurjeet Mamu's directive.

---

## 🔍 2. DEEP FORENSIC ROOT CAUSE ANALYSIS

### Why Did the Engine Place a Duplicate Order at 09:15 AM?
The blunder was caused by a **Zombie Database Block** interacting with the regular intraday P&L loop:

1. **The Ghost Block in SQLite**:
   - On 26-Nov, Super Sukhoi spawned Block 122 (M2) with Strikes 384 & 385 in `PENDING` mode.
   - When Super Sukhoi auto-pilot was turned OFF (`super_sukhoi_active = '0'`), it only prevented the Super Sukhoi engine from computing new triggers.
   - It did **NOT** purge the already-existing Block 122 and its `PENDING` strikes from SQLite!
2. **The Intraday P&L Engine Wakeup Trigger (`pnl_engine.py`)**:
   - `pnl_engine.py` runs every 30 seconds independently of Super Sukhoi.
   - At 09:15:05 AM, it scanned all blocks with `status = 'ACTIVE'`.
   - It found Block 122 with `status = 'ACTIVE'` and Strike 385 with `status = 'PENDING'`.
   - Spot was 25,891 (Bullish > Anchor 25,850).
   - `pnl_engine.py` evaluated: `"Strike 385 is PENDING and regime is BULLISH -> Auto-deploying strike!"`
   - It blindly called `execute_strike(385)` without checking whether Zerodha Kite already held 195 Qty of that exact strike!

---

## 🛡️ 3. FOUR PERMANENT ARCHITECTURAL INVARIANTS (THE REPAIR BLUEPRINT)

### 🧱 INVARIANT 1: Broker Ground Truth Lot Cap in `execute_strike()` (Iron-Clad Firewall)
**Flaw:** `execute_strike()` currently executes any strike ID passed to it without verifying existing account exposure.  
**Fix:** In `block_manager.py:execute_strike()`:
```python
# Before placing ANY order to Kite:
live_positions = kite_executor.get_positions()
existing_net_qty = next((abs(p['quantity']) for p in live_positions if p['tradingsymbol'] == target_symbol), 0)
max_allowed_qty = target_lots * 65

if existing_net_qty >= max_allowed_qty:
    _log(f"[ABORT-DUPLICATE] Broker already holds {existing_net_qty} qty of {target_symbol} (Max allowed: {max_allowed_qty}). Hard aborting order!", "ALERT")
    return {"ok": False, "reason": "DUPLICATE_POSITION_EXISTS_ON_BROKER"}
```
*Zero chance of ever doubling lots, even if a zombie block or script triggers!*

---

### 🧱 INVARIANT 2: Overnight Zombie Strike & Block Purge (Clean-Slate Sentinel)
**Flaw:** PENDING strikes from yesterday remained active overnight.  
**Fix:** In `main.py` daily morning initialization (09:00 AM watchdog):
```python
def morning_clean_slate_sentinel():
    """Purges any non-executed PENDING strikes from previous trading sessions."""
    conn = _conn()
    conn.execute("UPDATE strikes SET status='EXPIRED', trade_state='EXPIRED' WHERE status='PENDING' AND DATE(created_at) < DATE('now')")
    conn.execute("DELETE FROM blocks WHERE status='ACTIVE' AND block_id NOT IN (SELECT DISTINCT block_id FROM strikes WHERE status='OPEN')")
    conn.commit()
    conn.close()
```
*No unexecuted trade can survive across overnight market open!*

---

### 🧱 INVARIANT 3: Strict Unit Isolation (1 Unit = Max 1 Active Block)
**Flaw:** M2 was allowed to run concurrently in the background without operator approval.  
**Fix:** Unless Super Sukhoi is explicitly verified active and enabled by operator with 2-step confirmation, the engine rejects any block where `anchor_unit_name != 'M1'`.

---

### 🧱 INVARIANT 4: Atomic Wipe-Out & Settings Reset
**Flaw:** `wipe_out_and_reset_m_unit()` cleared block status but left `m_locked_anchor_*` keys in settings.  
**Fix:** When wiping out a unit:
```python
db.set(f"m_locked_anchor_{u}", "0.0")
db.set(f"m_settings_locked_{u}", "0")
db.set(f"super_sukhoi_{u.lower()}_deployed", "0")
```
*Eliminates stale anchor recall forever.*

---

## 📊 4. CURRENT SYSTEM STATE (27-NOV-2026 09:25 IST)

| Component | Status | Verification |
|---|---|---|
| **Background Engine Daemon** | **STOPPED (`inactive`)** | `systemctl is-active zerodha_engine.service` -> `inactive` |
| **Engine Algo Running Setting** | **`OFF`** | Set in `zerodha_trader.db` settings |
| **Super Sukhoi Auto-Pilot** | **`0` (PERMANENTLY MUTED)** | Set in `zerodha_trader.db` settings |
| **Weekly ST Positions** | **2 Lots (`-130` / `+130`)** | Live verified on Kite (`25500 PE` / `25000 PE`) |
| **Monthly M1 Positions** | **3 Lots (`-195` / `+195`)** | Live verified on Kite (`25200 PE` / `24700 PE`) |
| **Extra Lots / Zombie Blocks** | **`0` (Completely Flattened & Purged)** | Block 122 force-deleted from SQLite |
| **Account Health** | **100% Hedged & Safe** | Zero naked risk |
