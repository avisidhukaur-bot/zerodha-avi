# 🏛️ PRODUCT DEVELOPMENT FILE — SUPER SUKHOI ENGINE (V7.0)
## **Custom Implementation Architecture for Cheenna Zerodha**
> **Target Environment**: `c:\Users\Dell\Desktop\cheenna zerodha`  
> **Host / User**: Cheenna (Chhoti Bahan Edition) | Supervisor: Gurjeet Mamu  
> **Broker Integration**: Zerodha KiteConnect REST API (`kite_executor.py`)  
> **Protocol**: Gurjas's Lego System Protocol (`[DIAGNOSE] ➔ [BLUEPRINT] ➔ [APPROVAL] ➔ [CODE] ➔ [VERIFY]`)  
> **Date**: 26-Oct-2026 | Document Version: `7.0.1-CHEENNA`

---

## 📌 1. EXECUTIVE SUMMARY & CONTEXT

Gurjeet Mamu has delivered the **Super Sukhoi Autonomous Laddering Engine (V7.0)** specifications to transform the Directional M-Unit Architecture (`M1`, `M2`, `M3`) into a 100% automated, fire-and-forget directional laddering machine.

### Core Objective
Instead of manually monitoring Nifty spot and manually configuring or triggering `M2` or `M3`, Cheenna simply sets `M1` in the morning (Anchor Price $A_1$, Expiry, and Lots), clicks **`[ 🚀 ACTIVATE SUPER SUKHOI AUTO-MODE ]`**, and the engine:
1. **Autonomously Monitors** live Nifty Spot every 30 seconds.
2. **Auto-Spawns Tier 1 (`M2 UP` or `M2 DOWN`)** if Nifty moves $\pm 2.00\%$ from $A_1$.
3. **Auto-Spawns Tier 2 (`M3 UP` or `M3 DOWN`)** if Nifty moves $\pm 4.00\%$ from $A_1$ (provided M1 is still active).
4. **Enforces Compulsory Hedge Protection**: Zerodha Buy Hedge is placed **FIRST** (margin relief), followed by Short Leg **SECOND**.
5. **Decouples Midday 25% Stop-Loss**: Eliminates whipsaw stop-outs; positions are protected by the pre-bought 500-pt hedge helmet and evaluated at 14:57 IST EOD.

---

## 🔍 2. DIAGNOSTIC AUDIT: CHEENNA'S CODEBASE VS V7.0 SPECS

A comprehensive audit of `c:\Users\Dell\Desktop\cheenna zerodha` reveals the following readiness status:

| Component | Current State in `cheenna zerodha` | V7.0 Requirement | Status / Action Needed |
|---|---|---|---|
| **Holiday / Weekend Guard** | `utils.py` contains `NSE_HOLIDAYS_2026`, `is_trading_day()`, `is_market_hours()` | Market session guard to silence off-hours engine cycles and alerts | ✅ **85% Complete** (Needs small helper `is_market_session_active()`) |
| **M-Unit Auto-Hunter** | `inspect_m_unit_candidates()` in `block_manager.py` (V6.0/V6.3) | Scans EVEN 100-multiples for target premium ~₹200 with 500-pt hedge | ✅ **100% Ready** (Direct drop-in reuse) |
| **M-Unit Execution** | `deploy_or_update_m_unit()` in `block_manager.py` | Buy hedge first ➔ Sell leg second with live LTP anchor sync | ✅ **100% Ready** (Direct drop-in reuse) |
| **Stop-Loss Policy** | 25% SL auto-computed and enforced | Decouple SL: Add `m_stoploss_mode` (`"DISABLED"` default) | 🟡 **Needs Brick 2** (Add toggle in `db.py` & guard in `pnl_engine.py`) |
| **Super Sukhoi Engine** | Not yet created | `super_sukhoi_engine.py` autonomous supervisor loop | 🔴 **Needs Brick 3** (Create single module) |
| **Engine Loop Hook** | `main.py` has pulses for 11:15, 13:15, 14:57, 15:01, 15:10, 15:13 | Add 30s Super Sukhoi evaluation hook inside trading hours | 🟡 **Needs Brick 4** (Clean 10-line hook) |
| **Dashboard UI** | `app.py` has Directional Cockpit (Tab 1, Port 9007) | Super Sukhoi HUD card, Radar telemetry & 2-step confirmation modal | 🟡 **Needs Brick 5** (Add UI card in Cockpit) |
| **Automated Verification**| Existing test scripts | Dedicated test suite `test_super_sukhoi_zerodha_v7.py` | 🔴 **Needs Brick 6** (Create validation test) |

---

## 📐 3. MATHEMATICAL TRIGGER BANDS & SCALING MATRIX

Derivation based on Cheenna's Seed Unit `M1` Master Anchor Price ($A_1$):

$$\Large A_1 = \text{Cheenna-Defined M1 Master Anchor Price}$$

### Concrete Example ($A_1 = ₹22,650.00$):

| Tier & Direction | Mathematical Formula | Trigger Level ($A_1 = 22,650$) | Autonomous Execution on Kite |
|---|---|---|---|
| **Tier 1: `M2 UP`** | $\text{round}(A_1 \times 1.020, 2)$ | **₹23,103.00** | Inherit M1 Expiry & Lots ➔ Anchor = ₹23,103 ➔ Buy Hedge FIRST ➔ Sell PE Leg SECOND |
| **Tier 1: `M2 DOWN`**| $\text{round}(A_1 \times 0.980, 2)$ | **₹22,197.00** | Inherit M1 Expiry & Lots ➔ Anchor = ₹22,197 ➔ Buy Hedge FIRST ➔ Sell CE Leg SECOND |
| **Tier 2: `M3 UP`** | $\text{round}(A_1 \times 1.040, 2)$ | **₹23,556.00** | Inherit M1 Expiry & Lots ➔ Anchor = ₹23,556 ➔ Deploy Second Bull Put Spread *(if M1 active)* |
| **Tier 2: `M3 DOWN`**| $\text{round}(A_1 \times 0.960, 2)$ | **₹21,744.00** | Inherit M1 Expiry & Lots ➔ Anchor = ₹21,744 ➔ Deploy Second Bear Call Spread *(if M1 active)* |

### Invariant Rules
1. **Unidirectional Lockout**: If `M2 UP` triggers, `M2 DOWN` is locked out permanently for that deployment cycle.
2. **M1 Prerequisite for M3**: `M3` will only deploy if `M1` is still `ACTIVE` and open on Kite. If M1 was manually squared off or stopped, M3 deployment is suppressed.
3. **Even-100 Series Enforcement**: All strikes chosen will have `strike % 100 == 0`, ensuring zero collision with OS 50-ending series (`strike % 100 == 50`).

---

## 🧱 4. GURJAS'S SINGLE-BRICK IMPLEMENTATION ROADMAP

Following the strict protocol, changes are isolated into 6 modular bricks:

```
[Brick 1: Guards] ➔ [Brick 2: SL Decouple] ➔ [Brick 3: Super Sukhoi Engine] ➔ [Brick 4: Loop Hook] ➔ [Brick 5: UI HUD] ➔ [Brick 6: Test Suite]
```

### Brick 1: Session & Holiday Guard
- **File**: [utils.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/utils.py)
- **Enhancement**: Ensure `is_market_session_active()` strictly returns `False` on weekends, NSE 2026 holidays, and outside 09:15–15:30 IST.

### Brick 2: Stop-Loss Decoupling & DB Settings
- **Files**: [db.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/db.py), [pnl_engine.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/pnl_engine.py)
- **Enhancement**: Add `m_stoploss_mode` (`"DISABLED"` / `"ENABLED"`). Default to `"DISABLED"`. When `"DISABLED"`, the aggressive intraday 25% SELL exit is bypassed, allowing natural theta harvesting protected by the 500-pt hedge helmet.

### Brick 3: Super Sukhoi Autonomous Supervisory Engine
- **File**: `super_sukhoi_engine.py` (New Module)
- **Functions**:
  - `get_super_sukhoi_status() -> dict`: Returns active state, seed anchor, M2/M3 trigger levels, and deployment states.
  - `activate_super_sukhoi(m1_anchor, expiry, lots) -> dict`: Arms Super Sukhoi in DB.
  - `deactivate_super_sukhoi() -> dict`: Disarms Super Sukhoi back to Manual Cockpit mode.
  - `evaluate_super_sukhoi_cycle() -> dict`: Runs every 30s during market hours. Checks live Nifty Spot against $\pm 2\%$ and $\pm 4\%$ trigger bounds and fires `bm.deploy_or_update_m_unit()` autonomously.

### Brick 4: Background Loop Integration
- **File**: [main.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/main.py)
- **Enhancement**: Inside `start_engine_loop()`, call `super_sukhoi_engine.evaluate_super_sukhoi_cycle()` every 30s during active market hours.

### Brick 5: Streamlit Cockpit Radar UI (Port 9007)
- **File**: [app.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/app.py)
- **Enhancement**: Render the Super Sukhoi HUD Card in Tab 1 (Directional Cockpit):
  - Live Status Badge (STANDBY / ARMED / ACTIVE).
  - Calculated M2 and M3 trigger prices dynamically shown.
  - High-visibility `[ 🚀 ACTIVATE SUPER SUKHOI AUTO-MODE ]` button with 2-step confirmation modal.
  - Quick `[ 🛑 DEACTIVATE ]` toggle.

### Brick 6: Automated Sanity Test Suite
- **File**: `test_super_sukhoi_cheenna_v7.py`
- **Coverage**:
  - Verification of mathematical trigger bounds ($\pm 2\%$, $\pm 4\%$).
  - Unidirectional lockout logic.
  - Database persistence and state transitions.
  - Holiday/weekend silence guard.

---

## 🗄️ 5. DATABASE SCHEMA ATTRIBUTES (`zerodha_trader.db`)

Key-value attributes stored in the SQLite `settings` table:

| Attribute Key | Default Value | Description |
|---|---|---|
| `super_sukhoi_active` | `"0"` | `"1"` = Super Sukhoi Auto-Mode ON, `"0"` = Manual Mode |
| `super_sukhoi_m1_anchor` | `""` | Seed Anchor price ($A_1$) locked at activation |
| `super_sukhoi_m1_expiry` | `""` | Expiry date inherited by M2/M3 |
| `super_sukhoi_m1_lots` | `"1"` | Number of lots inherited by M2/M3 |
| `super_sukhoi_m2_deployed` | `"0"` | `"1"` once M2 has been automatically deployed |
| `super_sukhoi_m2_direction`| `""` | `"UP"` or `"DOWN"` indicating which wing was triggered |
| `super_sukhoi_m3_deployed` | `"0"` | `"1"` once M3 has been automatically deployed |
| `super_sukhoi_m3_direction`| `""` | `"UP"` or `"DOWN"` indicating which wing was triggered |
| `super_sukhoi_activated_at` | `""` | Timestamp of activation |
| `m_stoploss_mode` | `"DISABLED"` | Decoupled SL policy (`"DISABLED"` harvests theta with 500-pt hedge) |

---

## 🎯 6. CHEENNA'S DAILY OPERATING WORKFLOW (POST-UPGRADE)

```
09:00 AM: Launch Desktop App (RUN_CHHOTI_BAHAN_ZERODHA_OS.bat)
   │
   ▼
09:15 AM: Verify M1 Anchor Price (e.g. ₹22,650) & Lots in Cockpit
   │
   ▼
09:16 AM: Click [ 🚀 ACTIVATE SUPER SUKHOI AUTO-MODE ] ➔ Confirm
   │
   ▼
100% Done! Close laptop lid or do daily tasks.
Super Sukhoi will automatically deploy M2 and M3 if market moves!
```

---

## 📋 7. NEXT ACTIONS & APPROVAL PROTOCOL

Per Gurjeet Mamu's instruction:
> *"please review this and make a product development file which is suitable to my system and tell me what to do not change the code just way blueprint and product development file in detail"*

### What to do now:
1. **Review**: Gurjeet Mamu and Cheenna review this Blueprint & Product Development Plan.
2. **Approval (Step 3)**: Once Mamu/Cheenna confirm ("Approved" or "Proceed"), we execute Bricks 1 through 6 sequentially.
3. **No Code Tampered Yet**: In accordance with the Lego Protocol, zero production code has been altered.
