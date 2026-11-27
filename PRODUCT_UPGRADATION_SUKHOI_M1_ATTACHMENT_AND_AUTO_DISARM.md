# 🏛️ PRODUCT UPGRADATION SPECIFICATION
## SUPER SUKHOI V8.7.6 PARITY: M1-ATTACHMENT & AUTOMATIC DISARM ARCHITECTURE
> **Target System:** Bharat Zerodha Option Selling Engine (Sister's Account: `XK7125`)  
> **Reference Standard:** Bhaiya's Master System (`v8.7.6-SUKHOI-M1-CLOSE-AUTO-DISARM` — Gg Gg Delhi)  
> **Date:** 27-Nov-2026 09:35 IST  
> **Status:** BLUEPRINT READY FOR OPERATOR REVIEW (ZERO CODE CHANGES APPLIED YET)  

---

## 📊 1. SIDE-BY-SIDE ARCHITECTURAL COMPARISON

| Architectural Component | Bhaiya's Master System (`v8.7.6`) | Cheena's Current System (`XK7125`) | Required Action / Gap Analysis |
|---|---|---|---|
| **Super Sukhoi Lifecycle State** | **Strictly Attached to M1**: Super Sukhoi cannot exist as a standalone entity. It lives and dies with M1. | **Decoupled / Independent Flag**: `super_sukhoi_active` remained `1` even after M1 was closed or wiped out. | **ADOPT BHAIYA'S ARCHITECTURE**: Hook Super Sukhoi lifecycle strictly into M1 block status. |
| **M1 Close / Wipeout Hook** | **`_auto_disarm_sukhoi_if_m1()`** implemented in `block_manager.py`: The second M1 reaches `0` open strikes, `super_sukhoi_active` is forced to `0`, all anchor keys are wiped, and Telegram alert is sent. | **Missing (`False`)**: `block_manager.py` only called `db.unlock_m_unit_settings('M1')`, leaving Super Sukhoi armed and dangerous. | **IMPLEMENT `_auto_disarm_sukhoi_if_m1()`**: Insert hook in `close_strike()`, `kill_block()`, `delete_block()`, and `wipe_out_and_reset_m_unit()`. |
| **Stale Anchor Fallback in Radar & Cycle** | **Completely Removed**: If M1 active block does not exist, radar returns `anchor = 0.0` and cycle immediately disarms. | **Had Stale Fallback**: If active block was missing, code fell back to `state.get('m1_anchor')` which read the stale `₹25,225.0`. | **REMOVE ALL FALLBACKS**: If M1 active block is missing $\implies$ Immediate Disarm + Abort. Zero fallback to database cache. |
| **M1-Active Precondition Guard** | **Hard-Coded**: `evaluate_super_sukhoi_cycle()` queries live broker positions. If M1 has 0 open contracts on Kite, M2/M3 evaluation is 100% blocked and auto-disarms. | **Partial / Flawed**: Checked if M1 block existed, but did not enforce active broker contracts before trigger evaluation. | **HARD-CODE LIVE BROKER M1 GUARD**: Enforce broker ground truth check in `evaluate_super_sukhoi_cycle()`. |
| **Overnight Zombie Strike Protection** | **Daily Morning Sentinel (09:00 AM)**: Purges previous day's `PENDING` strikes so unexecuted orders cannot fire at 09:15 AM market open. | **Missing**: Zombie PENDING strikes remained in DB overnight, causing the 09:15 AM duplicate order today. | **IMPLEMENT MORNING PURGE**: Clean slate sentinel at 09:00 AM daily. |
| **Broker Net Exposure Cap in `execute_strike()`** | **Hard-Coded Ceiling**: Checks broker net qty before routing order. If net qty $\ge$ unit locked lots, order is rejected. | **Missing**: `execute_strike()` routed orders without cross-checking existing broker exposure. | **IMPLEMENT LOT CEILING**: Hard abort if broker already holds target quantity. |

---

## 🔍 2. THE THREE CODE BRICKS TO BE IMPLEMENTED (UPON APPROVAL)

### 🧱 BRICK 1: `super_sukhoi_engine.py` — Auto-Disarm & Stale Anchor Purge
Add `auto_disarm_super_sukhoi(reason)` and harden `evaluate_super_sukhoi_cycle()`:
```python
def auto_disarm_super_sukhoi(reason: str = "M1 Closed") -> None:
    """
    Hard-Coded Invariant (v8.7.6 Parity):
    Automatically shuts OFF Super Sukhoi, purges all stale anchor/trigger keys from DB,
    and ensures it will NEVER auto-resume until the operator manually clicks Activate.
    """
    db.set("super_sukhoi_active", "0")
    db.set("super_sukhoi_m1_anchor", "0.0")
    db.set("super_sukhoi_m2_anchor", "0.0")
    db.set("super_sukhoi_m3_anchor", "0.0")
    db.set("super_sukhoi_m2_deployed", "0")
    db.set("super_sukhoi_m3_deployed", "0")
    db.set("super_sukhoi_m2_cooldown_until", "0.0")
    db.set("super_sukhoi_m3_cooldown_until", "0.0")
    _log(f"[SUPER_SUKHOI] 🛑 AUTO-DISARMED: {reason}. All anchor memory purged.", "ALERT")
    try:
        telegram_bot.send_message(f"🛑 [SUPER SUKHOI AUTO-DISARMED]\nReason: {reason}\nStatus: OFF (Manual restart required).")
    except Exception:
        pass
```

### 🧱 BRICK 2: `block_manager.py` — Lifecycle Attachment to M1
Hook auto-disarm into every strike closure and block deletion:
```python
def _auto_disarm_sukhoi_if_m1(block_id: int):
    """If the affected block belongs to M1, inspect remaining open strikes; if 0, disarm Super Sukhoi."""
    b = db.get_block(block_id)
    if b and (b.get("anchor_unit_name") or "").strip().upper() == "M1":
        open_strikes = db.get_strikes_by_block(block_id, status_filter="OPEN")
        if len(open_strikes) == 0:
            import super_sukhoi_engine
            super_sukhoi_engine.auto_disarm_super_sukhoi("M1 has 0 open strikes remaining.")
```
*Hooked into:*
1. `close_strike()` (when remaining open strikes == 0)
2. `kill_block()`
3. `delete_block()`
4. `wipe_out_and_reset_m_unit("M1")`

### 🧱 BRICK 3: `block_manager.py:execute_strike()` — Iron-Clad Broker Lot Cap
```python
# Before sending ANY order to Kite API:
live_positions = kite_executor.get_positions()
existing_net = next((abs(p['quantity']) for p in live_positions if p['tradingsymbol'] == target_symbol), 0)
max_allowed = target_lots * 65

if existing_net >= max_allowed:
    _log(f"[ABORT-DUPLICATE] Broker already holds {existing_net} qty of {target_symbol} (Max: {max_allowed}). Order blocked!", "ALERT")
    return {"ok": False, "reason": "DUPLICATE_POSITION_ALREADY_EXISTS"}
```

---

## 🎯 3. SUMMARY OF SYSTEM HEALTH & STATUS RIGHT NOW

1. **Current State:**
   * VPS Engine Service: **STOPPED (`inactive`)**
   * `algo_running`: **`OFF`**
   * `super_sukhoi_active`: **`0`**
   * Live Broker Positions: **2 Lots Weekly ST + 3 Lots Monthly M1 (100% hedged, zero naked risk)**.
2. **Next Steps:**
   * Operator reviews this specification.
   * Upon explicit approval, we will apply Bricks 1, 2, and 3, run automated parity unit tests, and deploy to VPS via single-brick protocol.
