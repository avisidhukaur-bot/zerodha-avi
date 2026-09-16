# 🛠️ PRODUCT DEVELOPMENT CORRECTION SPECIFICATION

**Module:** Zerodha Option Selling Engine — Unit M1 & Strike Pricing Controller  
**Issue Reference:** Strike 24300 CE (Unit M1) Manual Stop Loss Overwritten by 25% Auto-Calculation  
**Date:** 09-Sep-2026  
**Status:** ✅ RESOLVED & VERIFIED  

---

## 1. Executive Summary & Problem Description

### What Happened:
The operator manually configured **Strike 24300 CE (Unit M1)** with:
- **Anchor Price:** ₹55.00
- **Manual Stop Loss Price:** ₹57.00

However, the system automatically changed the Stop Loss trigger to **₹68.75** (+25.0% on ₹55.00), ignoring the operator's explicit manual command of ₹57.00.

### Expected Behavior (The Invariant):
1. **Rule A (Manual Priority):** If the user manually inputs/edits a custom **Stop Loss Price (₹)** (e.g. ₹57.00), the system MUST strictly follow the user's manual command and NEVER overwrite it.
2. **Rule B (Auto-Calculation Fallback):** If the user does NOT manually specify a Stop Loss Price (left blank, 0, or default), ONLY THEN should the system automatically set the Stop Loss trigger to **+25% away** from Anchor/Fill price (i.e. $55.00 \times 1.25 = 68.75$).

---

## 2. Root Cause Analysis (Why Did This Happen?)

Deep inspection of the codebase identified 3 root causes:

1. **`execute_strike()` Invariant Overwrite (`block_manager.py:1162`)**:
   When a SELL order was filled on the exchange, `execute_strike()` executed:
   ```python
   # Old Code:
   sl_pct = float(updated_strike.get("sl_pct") or 25.0)
   exact_sl_price = fill_price * (1.0 + (sl_pct / 100.0))
   db.update_strike_sl_config(strike_id, sl_pct=sl_pct, sl_price=exact_sl_price)
   ```
   Even if the strike had an explicit manual `sl_price = 57.00` in the database, `execute_strike()` ignored `sl_price` and recalculated $55.00 \times 1.25 = 68.75$, immediately overwriting the database.

2. **Form Percentage Desynchronization (`app.py:1183`)**:
   In the "Add Strike to Block" and "Quick Edit" forms, when a user entered ₹57.00, the dropdown `sl_choice` stayed at `"25% (Standard)"`. When submitting, `sl_pct=25.0` was sent along with `sl_price=57.0`, causing downstream order execution to treat the position as a 25% rule instead of a manual rupee stop loss.

3. **Duplicate Function in `block_manager.py:1721`**:
   `block_manager.py` had a duplicate definition of `update_strike_anchor_price()` which modified anchor prices in isolation without maintaining atomic Stop Loss state.

---

## 3. Engineering Fix & Architectural Changes

### A. Execution Guard in `block_manager.py` (`execute_strike`)
The execution logic now checks if a manual `sl_price` is already present:
```python
fill_price = float(sell_result.get("fill_price", 0.0))
if fill_price > 0:
    cur_sl_price = float(updated_strike.get("sl_price") or 0.0)
    sl_pct = float(updated_strike.get("sl_pct") or 25.0)

    if cur_sl_price > 0:
        # User explicitly set a manual Stop Loss Price -> PRESERVE IT
        exact_sl_price = cur_sl_price
        sl_pct = max(0.1, ((exact_sl_price - fill_price) / fill_price) * 100.0)
        db.update_strike_sl_config(strike_id, sl_pct=sl_pct, sl_price=exact_sl_price)
        _log(f"[V5-SL-PRESERVED] Strike {strike['strike_price']} {strike['option_type']} SELL: Fill=₹{fill_price:.2f} -> Preserved Manual SL Price ₹{exact_sl_price:.2f} (+{sl_pct:.1f}%)", "OK")
    else:
        # Stop loss was not manually set -> Auto-compute +25% away
        exact_sl_price = fill_price * (1.0 + (sl_pct / 100.0))
        db.update_strike_sl_config(strike_id, sl_pct=sl_pct, sl_price=exact_sl_price)
        _log(f"[V5-SL-ANCHOR] Strike {strike['strike_price']} {strike['option_type']} SELL: Fill=₹{fill_price:.2f} -> SL Price set to ₹{exact_sl_price:.2f} (+{sl_pct:.0f}%)", "OK")
```

### B. Form Synchronization in `app.py`
1. When a user enters a manual Stop Loss price in rupees (e.g. ₹57.00), the UI calculates the exact percentage delta (`((57 - 55) / 55) * 100 = 3.64%`) and sends the synchronized `sl_pct` to backend functions.
2. In Quick Edit, editing `Anchor Price` or `Stop Loss Price` atomically updates both fields in SQLite database without any auto-override.

### C. Unified Single Source of Truth
Removed duplicate functions in `block_manager.py` so that `update_strike_price_and_sl()` is the authoritative atomic updater.

---

## 4. Verification Matrix

| Test Case | Inputs | Expected Output | Status |
|---|---|---|---|
| **1. Manual Custom SL** | Anchor = ₹55.00, SL = ₹57.00 | Stored `sl_price` = ₹57.00, executed SL trigger = ₹57.00 | ✅ PASS |
| **2. Default Auto SL** | Anchor = ₹55.00, SL = ₹0.00 (Default) | Auto-computed `sl_price` = ₹68.75 (+25%) | ✅ PASS |
| **3. Inline Quick Edit** | Edit Anchor=55, SL=57 in Unit M1 | DB retains Anchor=₹55.00, SL=₹57.00 | ✅ PASS |
| **4. PnL Auto-Exit Check** | Market LTP breaches ₹57.00 | Exit triggers at ₹57.00 (not waiting for ₹68.75) | ✅ PASS |
