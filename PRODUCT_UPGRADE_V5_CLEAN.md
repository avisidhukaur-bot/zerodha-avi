# PRODUCT UPGRADE V5: CLEAN INPUTS & ZERO-DEFAULT DEPLOYMENT SAFEGUARD
_Date: 11-Sep-2026 | Architecture: V5.0 "Old & Gold" Clean Edition_

---

## 🔍 1. Root Cause Diagnosis: Why Were Ghost / Unintended M1 Trades Happening?

### Problem A: Hardcoded Pre-filled Dummy Strikes & Fallback Anchors
In the previous deployment console, strike inputs were pre-populated with arbitrary default values:
- `CE Sell Strike` = `23600`, `CE Hedge Strike` = `23900`
- `PE Sell Strike` = `23000`, `PE Hedge Strike` = `22700`
- `Unit Pod` was defaulted to `M1` via a simple text input.
- Because `search_option_contract` had an attribute name mismatch with `search_option_symbol` in `kite_executor.py`, live LTP returned `0.0`.
- The system fell back to hardcoded dummy anchor prices: `CE Anchor = ₹75.00`, `CE Hedge = ₹15.00`, `PE Anchor = ₹75.00`, `PE Hedge = ₹15.00`.

### Problem B: Premature Armed Execution
When an operator opened the console or clicked deploy without explicit configuration:
- The pre-filled dummy strikes and M1 unit name created a new Block 1 (M1) in SQLite.
- The background daemon `zerodha_engine.service` detected `Status: ACTIVE` with `trade_state: OPEN`.
- The auto re-entry guard and execution cycles immediately began placing live market/limit orders on Zerodha!

---

## 🛠️ 2. Upgrades & Step-by-Step Corrections

### 1️⃣ Zero-Default Clean Inputs (No Auto Dummy Strikes)
- Strike price fields (`ce_sell_strike`, `ce_hedge_strike`, `pe_sell_strike`, `pe_hedge_strike`) start at **`0`** (Blank).
- The operator must explicitly type or step to the desired strike (e.g. `23700`).
- No dummy trades can ever be formed by accident.

### 2️⃣ Dynamic Real-Time LTP & Stop-Loss Auto Calculation
- Fixed `_fetch_opt_live_price` to reliably resolve Zerodha instruments via `search_option_symbol`.
- Added `search_option_contract = search_option_symbol` on `KiteExecutor` for full backward compatibility.
- **Dynamic Trigger Behavior**:
  - If Strike is `0`: Anchor and SL display `0.00`, preview states `⚪ Enter Strike Price above to fetch live LTP and SL`.
  - As soon as Strike `> 0`:
    1. Instantly queries Kite API for live LTP of that specific contract.
    2. Auto-populates Anchor Price with Live LTP.
    3. Auto-calculates exact Stop Loss price (₹) and percentage (+25% default or custom).
    4. Displays live badge with live LTP, anchor, and SL trigger.

### 3️⃣ Smart Unit Pod Selector (`M1`, `M2`, `M3`, `M4`, `M5`, `M6`)
- Replaced the error-prone text input with a clean dropdown selectbox: `["M1", "M2", "M3", "M4", "M5", "M6"]`.
- Automatically selects the next available unit (e.g. if M2 is active, default selection is `M3`).

### 4️⃣ Strict Pre-Deployment Validation Safeguard
Before placing any order or creating any block in SQLite:
- Checks if Sell Strike and Hedge Strike are `> 0`.
- Checks if Anchor Price is `> 0`.
- Validates that the contract exists in the security master.
- If invalid/empty, blocks deployment with a clear operator error and takes ZERO broker action.

---

## 🧱 3. Lego Deployment & Verification Workflow
1. **Local Implementation**: Update `app.py`, `kite_executor.py`, and test files.
2. **Local Verification**: Run all unit tests and simulation scripts to verify 100% pass rate.
3. **Lego Deployment**: Push clean package to VPS (`5.75.250.104:9007`) via `lego1_deploy.py`.
4. **Service Health Check**: Verify `zerodha_dashboard.service` and `zerodha_engine.service` status on VPS via `lego0_diagnose.py`.
