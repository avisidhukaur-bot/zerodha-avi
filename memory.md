# Zerodha Option Selling App — Permanent Memory
_Last updated: 08-Oct-2026 12:10 IST (TRI-BROKER PARITY & V8.2 ASYMMETRIC DUAL-EXPIRY HUNTER DEPLOYMENT)_

---

## 🔴 08-OCT-2026 11:15 IST PULSE FORENSIC AUDIT & V8.2 ASYMMETRIC DUAL-EXPIRY HUNTER UPGRADE

### 📋 1. Executive Summary & Problem Description
- **Audit Trigger:** At the 11:15 IST SuperTrend Pulse (2-Hour candle closed BEARISH at ~22,350 vs ST line ~22,736), the three sister option-selling engines demonstrated divergent behaviors:
  - **Zerodha & Kotak:** Successfully squared off their existing Bull Put spread (Position #25), but failed to deploy the opposing Bear Call spread.
  - **HDFC:** Completely failed to square off the open Bull Put spread (Position #5: Short `22350 PE` + Long `21850 PE`), throwing `POSITION_UNKNOWN` in logs, and also failed to deploy the Bear Call spread.

### 🔍 2. Deep Root-Cause Analysis
1. **HDFC Execution Blunder (Root Cause):**
   - In `_get_broker_short_state(sell_token, sell_strike, sell_option_type)` inside `weekly_st_engine.py`:
     - The function called `hdfc_executor.get_holdings()` instead of `hdfc_executor.get_positions()`.
     - `get_holdings()` in HDFC Sky exclusively queries Demat equity assets and delivery shares. Live intraday F&O derivatives are returned by `get_positions()`.
     - Furthermore, `hdfc_executor.is_logged_in` was inspected before calling `ensure_logged_in()`.
     - Consequently, `_get_broker_short_state` always returned `(POSITION_UNKNOWN, 0.0)`.
     - Under White Glass Broker Ground Truth fail-safe protocol, when a position is `UNKNOWN`, the engine refuses to take action to avoid duplicate or phantom orders. This prevented Position #5 from squaring off.
2. **Fresh Bear Call Entry Refusal Across All 3 Brokers (Root Cause):**
   - At 11:14 IST, Spot was ~22,350 while 2H SuperTrend was ~22,736.
   - The strike hunter looked for a Call strike paying ₹65–₹115 outside the SuperTrend Moat ($ST + 50\text{ pt} = \ge 22800$).
   - Current week (`13-OCT-2026`) safe Call strikes $\ge 22800$ had decayed down to ₹40.50 (well below the ₹65 floor).
   - Strike `22600 CE` was trading at ₹88.50, but was banned because it was below the SuperTrend resistance line (22,736).
   - In Next Week (`19-OCT-2026`), strikes $\ge 22800$ were also below ₹65, while the liquid ~₹95 strike (`22650 CE`) was also trapped behind the current week's 2-hour SuperTrend moat line!
   - Result: Hunter correctly protected the account from selling dangerous strikes in the current week, but had no mechanism to capture natural ₹80 theta in the next week.

### 🏛️ 3. Architectural Solution (V8.2 Asymmetric Dual-Expiry Hunter & Volatility Cascade)
- **Asymmetric SuperTrend Moat Rule**:
  - **Current Week (`primary_exp`)**: Strict SuperTrend Moat enforced ($ST \pm 50\text{ pt}$ buffer + Spot buffer).
  - **Next Week (`next_exp`)**: When current week safe strikes decay below ₹65, engine shifts to next week and **bypasses the current-week SuperTrend line**. Strike selection enforces **Spot OTM clearance only** ($Spot \pm 150\text{ pt}$ buffer). Strike `22650 CE` is 300 points OTM from Spot (~22,350), trades at ~₹95.50, with hedge `23150 CE` at ~₹17.50 $\implies$ **+₹78.00 Net Credit**.
  - **Deep Volatility Cascade (`Step 2b`)**: If next week safe strikes also decay below ₹65, engine cascades to the third (Monthly) expiry.
- **HDFC White Glass Broker Ground Truth Repair**:
  - Re-routed `_get_broker_short_state` to `hdfc_executor.get_positions()`.
  - Added mandatory `hdfc_executor.ensure_logged_in()`.
  - Manually squared off open Position #5 in live market via HDFC API (Short `22350 PE` covered @ ₹129.40, Hedge `21850 PE` exited @ ₹16.50; net F&O broker positions verified `0`).

### 🚀 4. Deployment & Live Verification Matrix (08-Oct-2026)
| System | VPS Remote Path | Dashboard Port | Systemd Services | Live Hunter Verified Result |
|---|---|---|---|---|
| **Zerodha OS** | `/root/BHARAT-SYSTEMS/ZERODHA-OS/` | **Port 9007** | `zerodha_engine`, `zerodha_dashboard` | `22650 CE` @ ₹96.10 / `23150 CE` @ ₹17.50 (+₹78.60 credit) ✅ |
| **Kotak OS** | `/root/BHARAT-SYSTEMS/KOTAK-OPTIONSELLING/` | **Port 9003** | `kotak_engine`, `kotak_dashboard` | `22650 CE` @ ₹95.55 / `23150 CE` @ ₹17.50 (+₹78.05 credit) ✅ |
| **HDFC OS** | `/root/BHARAT-SYSTEMS/HDFC-OPTIONSELLING/` | **Port 9004** | `hdfc_engine`, `hdfc_dashboard` | `22650 CE` @ ₹95.05 / `23150 CE` @ ₹17.20 (+₹77.85 credit) ✅ |

---

## 🔴 07-OCT-2026 EOD FORENSIC AUDIT & M1–M4 SYSTEM RESTORATION — 100% BROKER GROUND TRUTH PARITY

### 📋 Executive Summary
- **Audit Trigger:** Comprehensive operator review of today's execution logs, M1–M4 system health, V8.0/V8.1 upgrades, and broker synchronization.
- **Broker Live Reality (Kite Connect Ground Truth):**
  1. `NIFTY26OCT22800CE` | **SHORT 260 qty (4 lots)** @ avg ₹216.06 (LTP ₹191.15) — **M1 Sold Leg** (P&L: +₹6,477.25).
  2. `NIFTY26OCT23300CE` | **LONG 260 qty (4 lots)** @ avg ₹57.45 (LTP ₹49.05) — **M1 Hedge Leg** (P&L: -₹2,184.00).
  3. `NIFTY26O1922350PE` | **SHORT 195 qty (3 lots)** @ avg ₹85.50 (LTP ₹114.75) — **W1 Weekly ST Sold Leg**.
  4. `NIFTY26O1921850PE` | **LONG 195 qty (3 lots)** @ avg ₹25.50 (LTP ₹31.90) — **W1 Weekly ST Hedge Leg**.
  - All earlier Put legs (`22600 PE`, `22100 PE`) and OS1 legs were cleanly closed during midday trading hours.
- **Forensic Discovery & Permanent Fix:**
  - `test_m_unit_v8_parity.py` previously lacked SQLite database isolation (it set `os.environ['TESTING'] = '1'`, but `config.py` did not reroute `DB_PATH`). Running the test suite directly on VPS temporarily overwritten `zerodha_trader.db` with a 1-lot mock test block.
  - **Brick 1 (Test Isolation Armor):** `config.py` updated: `if os.environ.get("TESTING") == "1": DB_PATH = os.path.join(BASE_DIR, "test_isolated.db")`. `test_m_unit_v8_parity.py` now uses dedicated `setUpClass`/`tearDownClass` temporary database hooks.
  - **Brick 2 (Broker Ground Truth DB Restoration):** Restored Block #202 (M1 Unit, 4 lots, Monthly 27-Oct expiry, Bearish regime) and linked Strikes #340 (`22800 CE SELL`, `trade_state = "CONTINUED"`, 25% SL = ₹270.19) and #339 (`23300 CE HEDGE_BUY`, `status = "OPEN"`, 4 lots) with 100% fidelity.
  - **Brick 3 (Dual-Service Deployment & Verification):** Deployed to VPS, cleaned bytecode cache, restarted both `zerodha_engine.service` and `zerodha_dashboard.service` (Port 9007). Verified live P&L engine fetching LTP for both open strikes every 30 seconds. All 4 unit tests in `test_m_unit_v8_parity.py` pass 100% on VPS.

---

## 🔴 07-OCT-2026 V8.1 — OS SYSTEM STRIKE 50-ENDING SERIES UPGRADE

### 📋 Change Summary
- **Operator Request:** OS system strikes should end in 50 (22550, 22650, 22750, 22850...) so trades can be instantly identified as OS vs M-Unit by looking at broker terminal.
- **File Changed:** `os_engine.py` — `hunt_os_strike()` function only (1 code change).
- **Scope:** STRICTLY confined to Zerodha OS. HDFC not touched.

### 🏛️ The Change (V8.1)
**Old logic** — OS hunted ODD 100-multiples (22700, 22900, 23100...) — visually similar to M-Units.

**New logic** — OS hunts 50-ENDING 100-multiples (22550, 22650, 22750, 22850...):
```python
# V8.1
fifty_series = subset[(subset["strike"] % 100 == 50)].copy()
candidates_pool = fifty_series if not fifty_series.empty else subset
```

### 🔑 Visual Identification Rule (PERMANENT)
| Pattern | System | Example |
|---------|--------|---------|
| Ends in **00** | M-Unit (M1/M2/M3) | 22600, 22800, 23000 |
| Ends in **50** | OS System (OS1–OS5) | 22550, 22750, 22950 |
| Ends in **50** | OS Hedge (also 50) | 22850, 23050, 23150 |

- Zero-Clash with M-Units preserved mathematically. ✅
- Hedges automatically also end in 50 (sell_strike + 100-multiple = 50-ending + 100-multiple = 50-ending). ✅
- Monthly NIFTY liquidity verified — excellent. ✅

---

## 🔴 07-OCT-2026 FORENSIC AUDIT \u0026 V8.0 PRODUCTION UPGRADE — ASYMMETRIC ENTRY RESTORATION, ORPHAN HEDGE ARMOR \u0026 OPPORTUNITY RE-ENTRY


### 📋 07-Oct-2026 Incident & Operational Audit
1. **The Forensic Observation**:
   - Operator reported major losses and system blunders when Spot/RTP fell below the Magical Line (Master Anchor = 22,650):
     - **Magical Line Failure**: When Spot broke below 22,650 into Bearish territory, Call Side Selling (`22800 CE SELL`) was blocked from initiating because `22600 PE SELL` was already running!
     - **Orphan Hedge Dumping**: In HDFC at 09:16:02 IST, `22600 PE SELL` hit 25% SL and exited, but at 09:18:44 the engine illegally liquidated the protective hedge (`22100 PE HEDGE`).
     - **Re-Entry Paralyzed**: When premium cooled down, the engine failed to re-enter the Put trade.
2. **Root Cause Analysis**:
   - In `regime_engine.py` line 297 and `pnl_engine.py` line 888, a legacy blocker checked `if has_open_opposing and not is_3pm_or_later:` and skipped initiating the trend-aligned side. This directly violated the V6.0 Asymmetric Entry Rule!
   - In `block_manager.py` line 1405, `_async_close_hedge` was fired in a background thread because `close_hedge=True` was passed on intraday SL exits.
3. **Architectural Solutions Implemented (V8.0 Standard)**:
   - **Brick 1 (Asymmetric Entry Blocker Removal)**: In `regime_engine.py` and `pnl_engine.py`, removed `has_open_opposing` blockers. When Spot crosses below the Magical Line into BEARISH, `22800 CE SELL` immediately deploys as an asymmetric hedge. Running opposing Put trades are held peacefully under 25% SL protection until the 15:00 IST audit.
   - **Brick 2 (Absolute Orphan Hedge Armor Guard)**: In `block_manager.py` (`close_strike()`) and `pnl_engine.py`, enforced iron-clad intraday firewall: automated Stop-Loss exits hardcode `close_hedge=False`. Hedges are NEVER liquidated between 09:15 and 15:13 IST.
   - **Brick 3 (Opportunity Re-Entry Engine Hardening)**: When a trade hits SL, after 300s cooldown and premium cooldown ($LTP \le Anchor - Buffer$), auto-reenter reuses the existing OPEN hedge without duplicate buy orders.
   - **Brick 4 (Graceful Fallback)**: In `regime_engine.py`, if JIT Dynamic Hunter returns no candidates, it gracefully falls back to executing the pre-drafted pending strike in the block.
   - **Brick 5 (Automated Test Suite & 3-Broker Verification)**: Created `test_m_unit_v8_parity.py` covering all 4 invariant rules (100% PASS). Deployed live to VPS (`46.224.133.16`). Live executed `22800 CE SELL` @ ₹216.10 + `23300 CE HEDGE` @ ₹57.45 on Zerodha Kite; preserved orphan hedge #341 OPEN.

---

## 🔴 07-OCT-2026 FORENSIC AUDIT & V7.6 PRODUCTION UPGRADE — CLOSE BUTTON UNIFICATION & POD STATE SYNCHRONIZATION

### 📋 07-Oct-2026 Incident & Operational Audit
1. **The Forensic Observation**:
   - On 07-Oct, operator noticed confusion regarding closing M1/M2/OS units:
     - Outer cockpit/header buttons had 2-step verification and reset both broker legs and pod settings (`m_settings_locked_M1 = 0`).
     - Inner block card buttons (`✖ Close Strike`, `💥 Kill`) closed broker positions on Kite, but did NOT call `db.unlock_m_unit_settings()`. Consequently, positions were closed on broker, but the top cockpit still displayed `LOCKED & ARMED`.
     - In addition, inner close buttons lacked 2-step confirmation guards, making them prone to accidental triggers.
2. **Oct 6 & Oct 7 Log Audit Across Zerodha Engine & Kite API**:
   - **06-Oct**: OS1 overnight evaluation continued `22100 PE SELL` overnight (LTP ₹84.75 $\le$ NSE close line ₹136.90). W1 held Bearish spread Position #24 (`22850 CE SELL` + `23350 CE HEDGE_BUY`, 13-Oct Expiry, 3 lots = 195 qty) matching 2H SuperTrend.
   - **07-Oct 10:18 IST**: Unit M1 entered Bullish Put spread (Order [1] BUY `22100 PE` @ ₹93.73 hedge + Order [2] SELL `22600 PE` @ ₹230.73 sold leg, 260 qty = 4 lots).
   - **07-Oct 10:22 - 10:24 IST**: Operator executed wipe-out/square-off of M1 and yesterday's OS1 (Order [4], [5], [6], [8]). M1 and OS units reset to clean Draft Mode.
   - **07-Oct 11:14:01 IST**: Weekly ST-2H (W1) scheduled 11:15 AM Pulse Watchdog detected 2H SuperTrend flipped from BEARISH to BULLISH. Exited old Bearish spread (Order [9] & [10], Position #24, banking +₹214.50 profit). Shifted to 19-Oct next week expiry, and deployed new Bullish spread (Order [11] BUY `21850 PE` @ ₹25.50 hedge + Order [12] SELL `22350 PE` @ ₹85.50 sold leg, Position #25, 3 lots = 195 qty).
   - **Current Live State**: W1 Position #25 is holding peacefully. All other units (M1, M2, OS1–OS5) are 100% IDLE in Draft Mode.

### 🏛️ Architectural Solutions Implemented (V7.6)
1. **Brick 1: Inner Block 2-Step Confirmation & Synchronized Pod Reset**:
   - In `render_block_card`, `✖ Close Strike & Hedge` is now protected by a 2-step confirmation dialog (`⚠️ ARE YOU REALLY SURE? [ 🔥 YES ] [ ❌ Cancel ]`).
   - Added a dedicated `💥 Close Entire Block` button inside the card with 2-step confirmation. When confirmed, it calls `bm.wipe_out_and_reset_m_unit(uname)` (or `os_engine.wipe_out_and_reset_os_unit(uname)`), synchronously closing broker legs AND resetting the outer pod settings to clean Draft Mode.
2. **Brick 2: Automatic DB Pod Unlock on Final Strike Closure**:
   - Updated `bm.close_strike()`, `bm.close_hedge_strike_now()`, `bm.kill_block()`, and `bm.delete_block()`. Whenever the remaining open strikes in a block reach 0, the engine automatically unlocks the pod settings (`db.unlock_m_unit_settings` / `db.unlock_os_settings`), ensuring the UI cockpit is always in 100% synchronization with broker reality.
3. **Brick 3: Multi-Block Wipeout Support**:
   - `bm.wipe_out_and_reset_m_unit()` now loops through all matching active blocks for that unit (handling dual Call & Put blocks), force deletes them, and unlocks settings.
4. **Brick 4: Expiry Date Parsing Immunity**:
   - Added `parse_any_expiry_date(d_str)` and `normalize_expiry_display(d_str)` supporting both `%d-%b-%Y` and `%Y-%m-%d` seamlessly, preventing any date format crashes.
5. **Hard Invariant Preserved**:
   - The Weekly ST-2H (W1) button and controls remain strictly inside Tab 3 (`⚡ Weekly ST-2H Cockpit (W1 — V7.5)`), completely untouched.

---

## 🔴 30-SEP-2026 FORENSIC REPAIR — V6.3 JIT DYNAMIC AUTO-HUNTER, MINIMUM FLOOR GUARD & 14:55 ENTRY FREEZE

### 📋 30-Sep-2026 Incident — Timeline & Forensic Facts
1. **The Observation**:
   - On 30-Sep at 14:57:36 IST, Unit M1 executed a live Call sell: BUY 260 qty `23700 CE` @ ₹36.65, SELL 260 qty `23200 CE` @ ₹118.60 (net credit ₹81.95).
   - Operator was surprised because M1 had a Target Premium of **₹200**, yet it sold at ₹118.60, and entered just 3 minutes before 3:00 PM.
2. **Root Causes**:
   - **Stale Strike Execution (Gap between UI & Daemon)**: `23200 CE` was drafted 30 hours earlier (29-Sep 09:24 AM) when Spot was 22,666 and premium was ₹163.20. When Nifty fell to 22,638, the premium decayed to ₹118. `pnl_engine.py` only checked `ltp <= anchor_price` and executed the stale strike without re-hunting.
   - **Timing Disconnect**: `MASTER_DECISION_TIME` was 14:57, but `ACTIVE_TRADING_CUTOFF_TIME` was 15:13. The moment the 14:57 decision squared off the losing Put leg, the intraday loop treated the unit as having zero open opposing legs and immediately deployed the pending Call leg at 14:57:36 IST!
3. **Permanent Architectural Repairs (V6.3)**:
   - **Brick 1: JIT Dynamic Auto-Hunter (`bm.hunt_and_execute_jit_m_strike`)**:
     Whenever an M-Unit wing triggers in `pnl_engine.py` or `regime_engine.py`, the engine reads `target_premium` (default ₹200), dynamically scans the live option chain for the EVEN 100-multiple closest to target premium, updates the pending strike/hedge in the database, and executes the fresh strike.
   - **Brick 2: Minimum Premium Floor Guard**:
     Hard floor enforced: $\text{min\_floor} = \max(100.0, \text{target\_premium} \times 0.70)$ (e.g. ₹140.0 for ₹200 target). Any candidate below this floor is rejected as decayed junk.
   - **Brick 3: 14:55 / Post-3PM Entry Freeze**:
     In `pnl_engine.py` and `regime_engine.py`, fresh pending auto-entries for M-units are strictly blocked once time is $\ge$ 14:55 IST or if `last_3pm_decision_date == today`.
   - **Brick 4: Atomic DB Details Update (`db.update_strike_details`)**:
     Added atomic SQLite function to update `strike_price`, `anchor_price`, `sl_price`, `sl_pct`, and `lots` simultaneously.

---

## 🔴 29-SEP-2026 FORENSIC AUDIT — M1 CALL SELLING TIMING & 5-MIN STAY ANALYSIS

### 📋 29-Sep-2026 Incident — Timeline & Forensic Facts
1. **09:15 to 09:24 IST**:
   - Market opened at **22,732.45** (High: 22,753.20, Low: 22,656.20).
   - Spot Nifty was oscillating above 22,660.
   - **No active M1 block existed** in the database during this period.
2. **09:24:27 IST**:
   - Operator deployed Block 188 (Unit M1) with Anchor = **22,660.0**, Buffer = **15.0 pts**, Lots = **4**.
   - Live Nifty Spot was **22,666.90** (Above Anchor 22,660) $\implies$ Evaluated as **BULLISH**.
   - At **09:24:30 IST**, Bullish leg was executed on Zerodha Kite:
     - BUY 260 qty `22000 PE` @ ₹99.35 (Hedge)
     - SELL 260 qty `22500 PE` @ ₹210.05 (Sold leg)
   - Call wing (`23200 CE SELL` + `23700 CE HEDGE`) was placed into `PENDING`.
3. **09:25 to 09:27 IST**:
   - Spot Nifty broke down below 22,660 and breached the 15-pt buffer (`22,660 - 15 = 22,645`).
   - At **09:27:46 IST**, 30-second cycle detected Spot at **₹22,643.25** $\implies$ Flipped regime to **BEARISH**.
4. **09:27:48 to 09:27:50 IST**:
   - `pnl_engine.py` evaluated the `PENDING` Call strike: LTP ₹155.50 $\le$ Anchor ₹163.20.
   - Executed live on Zerodha Kite at **09:27:50 IST**:
     - BUY 260 qty `23700 CE` @ ₹50.25 (Hedge)
     - SELL 260 qty `23200 CE` @ ₹155.60 (Sold leg)
   - Result: Both Put and Call legs became simultaneously `OPEN` in Unit M1.

### 🔍 Root Causes of Operator's Concern ("Itna late kyun tha?"):
1. **Block Deployment Time**: Unit M1 was deployed at **09:24:27 IST**, not at market open (09:15). Prior to 09:24:27, the engine was completely idle because no block was active.
2. **Absence of 5-Minute Stay Confirmation Timer in Code**:
   - Operator's Rule: Spot must stay below `Anchor - 15 pts` for **5 full minutes** before triggering the opposing side.
   - Code Reality: No timer existed. The regime flipped instantly on a single 30-second tick when Spot crossed 22,645.
3. **Internal Code Logic Contradiction**:
   - `regime_engine.py:239` explicitly skipped CE deployment to avoid dual-sided strangles (`has_open_opposing` guard).
   - However, 2 seconds later in the same cycle, `pnl_engine.py:857`'s generic pending-entry check executed the CE sell because its regime permission check did not enforce `has_open_opposing`.

---


## 🔴 V6.1 M-UNIT 1-CLICK DEPLOY REPAIR (25-SEP-2026)

### 📋 25-Sep-2026 Incident — Forensic Report
- **Observation**: Operator clicked `🚀 Execute Qualified Now (Manual Deploy)` in M1 Cockpit at 09:47 IST, but Streamlit crashed with:
  `AttributeError: 'KiteExecutor' object has no attribute 'get_nifty_spot_ltp'`.
- **Root Cause Analysis**:
  1. `block_manager.py:2739` called `kite_executor.get_nifty_spot_ltp()` instead of `kite_executor.get_nifty_spot()`.
  2. `kite_executor.py` only defined `get_nifty_spot()`, causing an unhandled `AttributeError`.
  3. Secondary Hidden Bug: Line 2848 invoked `execute_strike(target_sid, ignore_cooldown=True)`, but `execute_strike` in `block_manager.py` did not accept `ignore_cooldown` or `**kwargs` (`TypeError`).
  4. Tertiary Hidden Bug: `db.create_block()` expected `custom_lots`, while `deploy_or_update_m_unit()` passed `recommended_lots=lots` (`TypeError`).
  5. Quaternary Guard: In `deploy_or_update_m_unit()`, the target strike's anchor price is now auto-refreshed with real-time LTP right before `execute_strike()` so slight market fluctuation between "Preview" and "Execute" never falsely triggers the `exit_threshold` buffer block.
- **Permanent Fixes Applied**:
  - `kite_executor.py`: Added `get_nifty_spot_ltp(self, force_refresh: bool = False)` alias delegating to `get_nifty_spot()`.
  - `block_manager.py`:
    - Updated line 2739 to `live_spot = kite_executor.get_nifty_spot()`.
    - Updated `execute_strike(strike_id: int, ignore_cooldown: bool = False, **kwargs)`.
    - Updated `deploy_or_update_m_unit()` to pass `custom_lots=lots`, synchronize block regime with trend side, and refresh live LTP before execution.
  - `db.py`: Added `recommended_lots: Optional[int] = None, **kwargs` to `create_block()`.
  - Added full test suite `test_v6_m_unit_deploy.py` (4/4 passed).

---

## 🔴 V6.0 ASYMMETRIC M-ENGINE — 24-SEP-2026 FORENSICS & PERMANENT RULES

### ⚖️ IRON LAW — Trade Closure Timing (NEVER CHANGE)
1. **Square-off / Close decisions happen ONLY in the EVENING: 15:00–15:05 IST (3:00 PM).**
2. **The ONLY intraday exception is a 25% Stop-Loss hit** on the sold leg (autonomous, runs every 30 seconds).
3. **NO other mid-day close is permitted.** Not on spot crossings. Not on regime flips. Not manually by engine logic.
4. **Orphan hedges** (hedge left after an intraday SL-hit) are closed ONLY in the 15:10–15:25 IST orphan audit window.

### 📋 24-Sep-2026 Incident — Forensic Report

#### Incident 1 — PE Side Blocked (Apparent, NOT a bug)
- **Observation**: At ~12:30 PM, CE side was active but PE side appeared dormant.
- **Root Cause**: Spot Nifty had fallen BELOW the Master Anchor. M1 Single-Directional Regime Guard evaluated `BEARISH` → PE selling is correctly **LOCKED / STANDBY** to prevent selling puts in a falling market.
- **Verdict**: ✅ **100% NORMAL BEHAVIOUR** — No bug. This is the M1 regime guard working as designed.
- **Rule**: When Spot < Anchor → BEARISH → CE selling ALLOWED, PE selling BLOCKED. This is by design.

#### Incident 2 — Wrong-Side Call Sell at 12:03 PM
- **Observation**: At 12:03 PM, engine executed a **CE SELL** which was the wrong direction.
- **Root Cause**: OS rules were being mixed with M1 rules. The engine momentarily followed OS execution logic instead of M1 regime-gated logic.
- **User Instruction**: "Don't follow OS rules — only follow M1/M2/M3 rules. Purge this trade."
- **Action Taken**: At 12:31 PM, the wrong CE trade was manually squared off via script (+₹806 profit). This was the only justified mid-day close (operator-authorised removal of an erroneous trade).
- **Verdict**: Operator-authorised cleanup, NOT a system auto-close. Rule not violated.

#### Incident 3 — CE Side Not Restarted After Manual Squareoff
- **Observation**: After the wrong CE was closed at 12:31 PM, market dropped further. A valid CE position should have been re-opened (CE sell is BULLISH-side, wrong after drop — actually system was correct to stay off CE).
- **User Intent**: "Start kar sakta hai, but close to evening mein hi karna hota hai."
- **Rule Confirmed**: Engine CAN open new trades during the day when regime aligns. It must NOT close existing trades until 3 PM (except SL).
- **Action**: User manually set up fresh anchor and trades for the afternoon session.

### 🏗️ V6.0 ASYMMETRIC M-ENGINE IDENTITY
- **Version Name**: V6.0 ASYMMETRIC M-ENGINE (replaces V5.0 OLD & GOLD branding)
- **Port**: 9007 (PERMANENT)
- **VPS**: `46.224.133.16` (PERMANENT)
- **Architecture**: Block Manager → M-Units (M1/M2/M3) + OS-Units (OS1/OS2)
- **Key Separation**: M-Units and OS-Units are COMPLETELY INDEPENDENT pipelines.
- **`os_engine` import**: `import os_engine` is present in `app.py` (line 39). Do NOT remove it.

### 🔧 block_manager.py — Live Broker Position Verification Fix
- **Bug Fixed**: `_find_existing_broker_order()` was reusing stale broker orders from old (already squared-off) positions.
- **Fix**: Added real-time `kite_executor.get_positions()` check. If instrument's net quantity = 0 on broker, the historical order match is ignored and a fresh order is placed.
- **Never Revert**: This prevents ghost re-linking of closed trades as if they were still open.

### 📌 M1 Regime Guard — Call Side Entry Rule
- **When Spot >= Anchor**: BULLISH → PUT selling OPEN, CALL selling BLOCKED
- **When Spot < Anchor**: BEARISH → CALL selling OPEN, PUT selling BLOCKED
- **Intraday Flip (midday)**: Does NOT close the currently running trade. Only gates new entries on the new side.
- **Evening Decision (15:00–15:02)**: Wrong-side trade is evaluated and squared off ONCE in the evening.
- **M1 can OPEN new trades during the day** when anchor/regime aligns — this is intentional and correct.

---


## 🚀 V5.5.1 STRIKE PREVIEW & LIVE UI RESILIENCE (23-SEP-2026)
Following forensic live market audit on 23-Sep-2026 across HDFC, Zerodha Kite, and Kotak Neo:

### 1. OS1 Odd 100-Multiples Strike Pool Separation:
- **Root Cause**: The 500-step filter (`step = 500` for DTE > 30) filtered out all strikes where `strike % 500 != 0`. When combined with the OS1 Odd Rule `(strike // 100) % 2 == 1`, it left only odd 500s (`22500, 23500, 24500, 25500`), creating a massive 1000-point jump between strikes and completely dropping all valid, liquid odd strikes (`23100, 23300, 23700, 23900`) priced around ₹105–₹150.
- **Permanent Fix**: OS selling candidates are strictly selected from all **ODD 100-multiples** (`(strike // 100) % 2 == 1` and `strike % 100 == 0`), giving a continuous 200-point ladder (`...23100, 23300, 23500, 23700, 23900...`). The 500-step rule remains strictly applied to the protective **Hedge/Helmet** leg (`sell_strike +/- 500`).

### 2. Streamlit KeyError 1279 Immunity & Informative Fallbacks:
- **Root Cause**: In `render_os_tab()`, lines assumed `h_ce['sell_strike']` existed whenever `inspection["ok"]` was True. When one wing had no eligible strikes, accessing `h_ce['sell_strike']` crashed Streamlit, preventing Active OS Pods Cockpit from rendering.
- **Permanent Fix**:
  - Guarded both Call and Put wing display boxes with `if h_ce.get("ok"): ... else: ...` and `if h_pe.get("ok"): ... else: ...`.
  - Added dedicated fallback cards when a wing is unqualified or skipped.
  - Added warning banner if neither wing qualifies, ensuring Streamlit never crashes.

### 4. Always-Visible Auto & Manual Deploy Console in Step 2:
- **Root Cause**: `STEP 2: EXECUTE OR ARM POD` was accidentally indented under `elif inspection and not inspection.get("ok"):`. This caused the Step 2 execution console (Pod selector, Manual Deploy button, and 3:00 PM Auto-Audit button) to be hidden whenever candidates qualified or before fetching. Furthermore, an `if not is_locked:` guard concealed the buttons in draft mode.
- **Permanent Fix**:
  - Unindented Step 2 to the top level of `render_os_tab()`, ensuring `STEP 2: EXECUTE OR ARM POD (AUTO & MANUAL DEPLOY)` is permanently visible.
  - Removed the lock gating that hid the buttons; clicking either `🚀 Execute Qualified Decaying Trade(s) Now (Manual Deploy)` or `⏱️ Arm for 3:00 PM Auto-Audit Only` automatically locks and persists draft settings in the DB and dispatches immediately.
  - Added clear state indicators (`LOCKED & ARMED` vs `Draft Mode (Auto-locks on Deploy)`).

### 5. Live Production Verification (23-Sep-2026):
- Deployed and verified on VPS (`46.224.133.16`) running systemd service `zerodha_dashboard.service` on Port 9007.
- Automated tests pass 100% (`test_v55_os_wipe_reset_and_odd_strikes.py`: 3/3 OK).
- Section 2 (Auto & Manual Deploy) and Section 3 (`📦 ACTIVE OS PODS (OPTION SELLING UNITS)`) render with 100% stability.

## 🚀 V5.5 UNIFIED SISTER UPGRADE & ARCHITECTURAL REPAIR (22-SEP-2026)
Following deep live market forensic audit on 22-Sep-2026 across HDFC, Kotak Neo, and Zerodha Kite:

### 1. Distinct Architecture & Time-Slot Separation: M-Units vs OS-Units:
- **M-Units (M1, M2, M3...) — Macro Directional Anchor System**:
  - Governed by Spot Nifty vs Master Anchor ($P_{\text{anchor}}$).
  - Intraday buying/entries can occur during market hours (09:15 to 15:00 IST) when conditions align or when operator deploys.
  - **Single-Directional Sanctity**: A unit NEVER holds opposing short legs simultaneously (NO dual 10-lot strangles).
  - **No Midday Opposing Close**: Midday spot crossings do NOT liquidate active trades. Opposing / wrong-side evaluation and square-off happens **strictly once per day at 15:00 to 15:02 IST**.
  - **Orphan Hedge Sanctity**: Intraday Stop-Loss exits leave the orphan hedge intact all day. Orphan hedges are evaluated and closed **strictly in the evening slot (15:10 to 15:25 IST)**.
- **OS-Units (OS1, OS2...) — Pure Option Momentum Line System**:
  - Governed by Option Contract LTP vs Yesterday's 3:00 PM Reference Line. Decoupled from Spot Nifty.
  - **100% Intraday Trading Silence**: Zero buying, zero selling, zero auto-hunting between 09:15 and 15:02 IST (only 1.382 SL monitored).
  - **Evening Execution Window**: All activity strictly occurs in the **15:02 to 15:05 IST window, ONLY ONCE PER DAY**.
  - **Post-15:05 Freeze**: Once evaluated/deployed, engine sleeps until next day 15:02 IST.

### 2. Permanent Removal of Midday Phase 2 Auto-Deploy Bug in `block_manager.py`:
- **Root Cause (HDFC 12:52 PM Incident)**: When Spot crossed Master Anchor at 12:51 PM, Phase 1 correctly deferred closing the open Put sell, but Phase 2 auto-deployed a closed Call strike (23900 CE), creating an illegal 10-lot dual-sided strangle that had to be dumped at 3:00 PM.
- **Permanent Fix**: Phase 2 Auto-Deploy in `evaluate_master_regime` is strictly gated:
  1. If the unit currently has an OPEN short leg on the opposing side, auto-deploying the other side is **100% BLOCKED**.
  2. Previously `CLOSED` strikes can NEVER be revived by an intraday spot flip. Auto-deploy on flip is strictly restricted to `PENDING` armed strikes or the 15:00-15:02 decision window.

### 3. OS Target Premium Nearest Hunting & ₹105 Minimum Floor (Zerodha Fix):
- **Root Cause (Zerodha 15:02 Incident)**: User locked Target Premium = ₹150. Auto Hunter sold 22000 PE for ₹30.10 and bought hedge at ₹16.65 (net credit ₹13.45), blocking high margin for peanut return.
- **Permanent Fix**:
  - Hunter selects the decaying contract **nearest to Target Premium** (can be slightly above or below, e.g. ₹135 - ₹165).
  - **Hard Minimum Floor (₹105)**: Set to $\max(105.0, \text{target\_premium} \times 0.70)$. If all decaying contracts in the chain are below ₹105, system logs `[HUNTER] ⚠️ NO TRADE QUALIFIED: All decaying strikes are below min floor ₹105 (Target: ₹150). Skipping junk trade.` and sits quiet with zero trade.

### 4. Anti-Same-Strike Churn & Cooldown in OS Engine (Kotak Fix):
- **Root Cause (Kotak 15:03 -> 15:05 Incident)**: 22500 PE was line-cut at 15:03, and 94 seconds later at 15:05 the Auto Hunter selected and re-sold 22500 PE with 2 lots!
- **Permanent Fix**: Any strike cut at 15:02 PM is blacklisted in database for the rest of the day. The OS hunter will NEVER re-enter a strike that failed the line audit on the same day.

### 5. Synchronous Instant Hedge Closure on Line Cut:
- In OS Engine, when a short leg is cut at 15:02 PM, `bm.close_strike(s_id, close_hedge=True)` closes the linked hedge synchronously in the exact same transaction, eliminating orphan hedges lingering for 11 minutes.

### 6. Streamlit Duplicate Widget Key Fix (Zerodha `app.py`):
- Scoped all `st.toggle("Enable Engine", key=...)` across tabs (`tab1`, `tab3`, `mgmt`) with unique prefixes, preventing `StreamlitDuplicateElementKey` crashes.

---

## 🛡️ V5.6 ANCHOR REFERENCE & NSE OFFICIAL CLOSE RESOLUTION (21-SEP-2026)
Following live incident audit on 21-Sep-2026 where `24000 CE SELL` was triggered at 15:02 IST due to a 5-day-old stale anchor:

### 1. Forensic Audit of 21-Sep `24000 CE` Incident:
- **Incident**: OS1 auto-deployed `NIFTY26OCT24000CE SELL` (2 lots) @ ₹118.90 + `24500 CE BUY` (2 lots) @ ₹35.55.
- **Root Cause**: `db.get_os_strike_anchor("NIFTY26OCT24000CE")` retrieved an undated anchor of `₹132.45` saved on **16-Sep (5 days prior)**.
- **Market Reality**: The real NSE previous close (Friday 18-Sep close from Kite API `ohlc["close"]`) was **₹116.00**. At entry, LTP was ₹118.90 (+₹2.90 above yesterday's close). The call was **rising**, not decaying. Stale cache misled the engine into believing it had decayed by ₹13.55.

### 2. Core Architectural Upgrades:
1. **Adoption of NSE Official Previous Day Close**:
   - The system permanently uses **NSE Official Previous Close (`ohlc["close"]` via Kite API)** as the authoritative yesterday reference price.
   - 100% immune to daemon downtime, weekend holidays, and token expirations.
2. **Date-Stamped Anchor Cache (`db.py`)**:
   - Anchors are saved with `os_anchor_date_{symbol} = YYYY-MM-DD`.
   - Any anchor not saved TODAY returns `0.0` (stale cache auto-invalidated), forcing fresh retrieval from Kite API.
   - `db.prune_stale_os_anchors()` automatically purges obsolete multi-day keys.
3. **Protection in `hunt_os_strike()`**:
   - Removed `set_option_anchor(sell_tsymbol, sell_ltp)` which previously overwrote anchors with live LTP.
   - Enforced `is_decaying = (sell_ltp < yesterday_anchor) if (yesterday_anchor > 0 and yesterday_anchor != sell_ltp) else False`. Never assumes decay if yesterday reference is missing.
4. **Daily 09:00 AM Anchor Refresh Watchdog (`main.py`)**:
   - Background daemon executes `os_engine.refresh_all_os_anchors()` daily after 09:00 AM IST to pre-cache all active and locked OS contracts.


## 🚀 V5.3a UNIFIED PRODUCTION RELEASE & FORENSIC UPGRADE (18-SEP-2026)
Following deep live market diagnostics across all three sister brokers (Zerodha OS, Kotak Neo, HDFC Sky), the engines are unified to `V5.3a`:

### 1. Kotak Engine Crash Loop Root Cause & Permanent Fix:
- Background daemon `kotak_engine.service` was trapped in an infinite crash loop (119+ failure restarts).
- **Cause**: `os_engine.py` was importing `from kite_executor import kite_executor`, which does not exist in Kotak Neo! Kotak uses native `kotak_neo_client.py` (`kotak_client`). This crashed `engine.py` on startup, paralyzing both OM (M1) and OS background trading.
- **Fix**: Replaced foreign imports with native `kotak_client`, verified clean bytecode compilation.

### 2. HDFC Duplicate Put Trade Root Cause & Permanent Fix:
- In HDFC Sky, Unit `OS1` held `23200 PE SELL` (2 lots) from 17-Sep (`trade_state = "CONTINUED"`).
- At 15:02 IST on 18-Sep, the 3:02 PM Auto-Deploy watchdog evaluated decaying options. Because legacy code lacked the **Side Overlap Guard**, it deployed a duplicate order: `23300 PE SELL` (2 lots) + `22800 PE HEDGE_BUY` (2 lots).
- **Fix**: Implemented the **Anti-Duplicate Side Overlap Guard**: checks `has_open_pe` and `has_open_ce` before deploying any wing. If Put or Call is already open in that pod, that side is strictly skipped.

### 3. Auto-Trade vs Manual Trade Separation (Operator Freedom):
- **15:02 IST Auto-Pilot**: Strictly limited to 1 execution per day via `db.has_os_auto_traded_today(pod_unit)` and `db.mark_os_auto_traded_today(pod_unit)`.
- **Manual Operator Execution (`btn_exec_os_now`)**: 100% unrestricted. Operators can manually execute trades anytime (1, 2, 3... times) with `is_manual=True`. Manual trades are NEVER blocked by the daily auto-trade limit counter.

### 4. Zero-Clash Strike Shield & Far-Month 500-Step Liquidity:
- Checks active strikes in M-Units (M1, M2, M3) and broker positions. Avoids collision by shifting away.
- DTE <= 30 days: 100-step multiples.
- DTE > 30 days: 500-step multiples for institutional liquidity.
- In Kotak and HDFC, market orders use Limit orders with a 10% safety buffer to eliminate NSE Error 1041.

### 5. Strict Locked Lots Enforcement:
- OS pods locked with `lots = 2` strictly maintain 2 lots across all legs and hedges. Default initialized to 2 lots.

---

## ⚡ V5.0 'OLD & GOLD' ARCHITECTURE UPGRADE (04-SEP-2026)
Following successful live verification on HDFC Sky V5.0, Zerodha OS is fully upgraded to V5.0 'Old & Gold' Architecture:

### Core V5.0 Invariants:
1. **Decoupled M1 Master Anchor (Peaceful Intraday Breathing)**:
   - Mid-day crossings of Master Anchor between 09:15 and 14:59 IST do **NOT** trigger trade closures.
   - Positions breathe freely during market hours to collect maximum theta decay without mid-day churn or unnecessary stop-outs.
2. **3:00 PM (15:00 IST) Continuation Decision**:
   - Evaluates Spot vs Master Anchor once daily at exactly 15:00 IST.
   - **Spot $\ge$ Anchor (Bullish)**: Continues PE Sell leg overnight (`trade_state = "CONTINUED"`), auto-closes opposing CE Sell leg & its active hedge.
   - **Spot $<$ Anchor (Bearish)**: Continues CE Sell leg overnight (`trade_state = "CONTINUED"`), auto-closes opposing PE Sell leg & its active hedge.
   - Orphan hedges remain untouched!
3. **Autonomous Configurable Stop-Loss Engine**:
   - Each trade calculates an autonomous Stop-Loss trigger: $SL = \text{Anchor} \times (1 + \frac{SL\%}{100})$ (configurable presets: 10%, 20%, 25%, or Custom).
   - SL engine monitors individual leg LTPs independently from Master Anchor spot fluctuations.
4. **Enforced Orphan Hedge Invariant**:
   - When a parent short leg hits its individual Stop Loss, only the short leg is closed (`trade_state = "SL_HIT"`).
   - The associated long hedge is **NEVER** auto-liquidated. It is preserved open as an orphan hedge.
   - Operators can manually lock realized profits at any time using the 1-Click `[ 💰 Lock Hedge Profit ]` button (`close_hedge_strike_now`).
5. **Unified Single-Window Setup Console ("Ek Hi Jagah Saari Chijen")**:
   - A single unified setup card at the top of the Options tab allows configuring the Master Anchor, Call Wing (Sell + Hedge + SL%), and Put Wing (Sell + Hedge + SL%) in one view.
   - On Deploy (`deploy_unified_master_unit`), the engine inspects live Spot vs Anchor and directionally deploys the favored wing into `OPEN` while arming the counter wing in `PENDING`.
6. **Re-entry Engine**:
   - Trades with `reentry_enabled = 1` reset to `trade_state = "OPEN"` once premium cools down below anchor after the mandatory cooldown period.
7. **Comprehensive Automated Verification**:
   - Fully verified via `test_v5_unified_console_and_3pm_decision.py` covering all 6 core invariants with 100% pass rate.

## 🛡️ V5.1 BROKER GROUND TRUTH & ACTIVE NAKED SHORT SENTINEL (04-SEP-2026)
Hardened against DB schema desynchronization and unhedged market risks, matching Kotak Neo V5.1 architecture:
1. **Live Broker Confirmation in `execute_strike()`**:
   - Before placing ANY short sell order, the system queries Zerodha Kite terminal positions via `kite_executor.get_net_positions()`.
   - If the linked Long Hedge is not verified active on the live broker terminal (even if SQLite DB says `OPEN`), the system immediately re-buys the hedge FIRST on the broker before executing the short sell order.
2. **3:00 PM Pre-Decision Broker Verification**:
   - At 15:00 IST during the Master Anchor decision, the continued short side MUST have an active long hedge verified on the live broker terminal.
   - If the long hedge is missing on the broker, overnight continuation is BLOCKED, the unhedged short leg is immediately auto-closed at market, and emergency Telegram/ntfy alerts are dispatched.
3. **Active Naked Short Sentinel (Heartbeat Guard)**:
   - Runs on every 30-second P&L cycle in `pnl_engine.py`.
   - Calculates total net broker positions: `naked_ce = short_ce - long_ce` and `naked_pe = short_pe - long_pe`.
   - If any naked short is detected on Zerodha terminal ($> 0$), fires an urgent Telegram alert and immediately auto-covers the unhedged short leg via market BUY (`reconcile_and_auto_protect_naked_shorts()`).
4. **Watchdog Protection Inversion Hard Block**:
   - In `sweep_orphan_hedges_now()` and EOD watchdog, under ZERO circumstances can a long hedge be closed if there is ANY live Short position on the broker terminal.
   - Preserves all protective hedges whenever the account is short.
5. **Automated Sentinel Verification**:
   - Verified via `test_v5_broker_ground_truth_and_sentinel.py` (4/4 tests passing: 100% OK).

### 🔄 Sister Broker Architecture Comparison (Kotak vs Zerodha):
| Feature / Layer | Kotak Neo Engine | Zerodha OS Engine | Parity Status |
|---|---|---|:---:|
| **Broker SDK** | `kotak_neo_client.py` (`get_net_positions`) | `kite_executor.py` (`get_net_positions`) | ✅ 100% Parity |
| **Dashboard Port** | Port `9003` | Port `9007` (Permanent) | ✅ Isolated & Intact |
| **Background Daemon** | `kotak_engine.service` | `zerodha_engine.service` | ✅ Separate Daemons |
| **Lot Size (Nifty)** | 65 | 65 | ✅ Identical |
| **Entry Sequence** | Buy Hedge FIRST on broker | Buy Hedge FIRST on broker | ✅ 100% Parity |
| **Live Broker Confirmation** | Verified in `execute_strike()` | Verified in `execute_strike()` | ✅ 100% Parity |
| **3:00 PM Continuation** | Live broker hedge confirmed | Live broker hedge confirmed | ✅ 100% Parity |
| **Active Naked Sentinel** | Heartbeat checks every cycle | Heartbeat checks every 30s | ✅ 100% Parity |
| **Watchdog Inversion Block** | Under zero circumstances close hedge if broker short > 0 | Under zero circumstances close hedge if broker short > 0 | ✅ 100% Parity |
| **EOD Sweep Window** | 15:20 to 15:40 IST | 15:36 to 15:45 IST (Trading cutoff 15:36) | ✅ Tailored to Zerodha |

### 🐛 Deep Research Bugs Audited & Resolved (04-Sep-2026):
1. **EOD Orphan Watchdog Bypass Bug (`pnl_engine.py`)**:
   - **Issue**: Legacy lines 887–935 ran a raw SQLite check for closed sells and scheduled hedges for `PENDING_CLOSE` without querying live broker positions.
   - **Fix**: Replaced with `bm.sweep_orphan_hedges_now()` which enforces Rule 7 Broker Ground Truth (aborts hedge liquidation if ANY live short is open on broker).
2. **Main Daemon EOD Sweep Hook (`main.py`)**:
   - **Issue**: Background loop lacked an explicit 15:36 IST EOD orphan sweep watchdog hook.
   - **Fix**: Added `E2` 15:36–15:45 IST watchdog in `main.py` ensuring the sweep is guaranteed once per calendar day.
3. **Autonomous SL Test Threshold (`test_brick9_auto_exit_cycle.py`)**:
   - **Issue**: Test used legacy $105.0$ LTP against a $100.0$ anchor, failing because V5.0 autonomous SL threshold was $125.0$ ($25\%$).
   - **Fix**: Updated LTP to $130.0$ to breach V5.0 threshold cleanly.
4. **Block Manager Signature Consistency (`block_manager.py` & `db.py`)**:
   - Added parameter to `create_block()` in both modules, fully supporting `PRESERVE`, `HOLD`, and `SQUARE_OFF` policies.

## 🎯 V5.2 DYNAMIC STOP-LOSS & NEARBY SL COLUMN UPGRADE (09-SEP-2026)
Upgraded to solve falling market decay (e.g. call premiums crashing by half) where operators need to lower Anchor Price and simultaneously tighten Stop Loss:
1. **Auto-Recalculating Stop Loss on Anchor Price Update**:
   - `bm.update_strike_anchor_price(strike_id, new_anchor, auto_recalc_sl=True)` & `db.update_strike_anchor_price(..., auto_recalc_sl=True)`.
   - When Anchor Price is updated (e.g. from ₹100 to ₹40), `sl_price` automatically recalculates to `round(new_anchor * (1 + sl_pct/100), 2)` (e.g. ₹50.00 at 25% SL) and `reentry_price` updates to `round(new_anchor - 1.0, 2)` (₹39.00).
   - Operators no longer have their stop loss stuck at legacy higher levels!
2. **Dedicated Nearby Stop-Loss Column in Quick Strike Settings**:
   - Reorganized into 4 columns: `[ ⚓ Anchor Price | 🎯 Stop Loss Price | 🔢 Lots | 🗑 Actions ]`.
   - Dedicated Stop Loss column allows entering any exact custom price (`new_sl_price`), displays live `%` distance from anchor, and includes 1-click preset buttons (`20% SL`, `25% SL`, `10% SL`).
   - Saving calls `bm.update_strike_sl(strike_id, new_sl_price, sl_pct)`.
3. **Top Cockpit Quick Access**:
   - Added `✏️ Adjust Anchor / SL` inline expander under each active sold leg in the All Open Units Cockpit so operators can adjust levels in 1-click without scrolling.
4. **Manual Strike Creation Support**:
   - `render_add_strike_form()` now provides configurable SL % selection (25%, 20%, 10%, Custom) and passes `sl_price` & `sl_pct` to `add_strike_to_block()`.
5. **Instant Telegram Alerts**:
   - `tg.alert_strike_anchor_updated()` & `tg.alert_strike_sl_updated()` provide instant push notifications on every adjustment.
6. **Automated Verification**:
   - Verified via `test_dynamic_sl_and_anchor_update.py` (4/4 tests passing: 100% OK).

## 🛡️ V5.3 BUFFER WALL & HYSTERESIS DEPLOY GUARD (16-SEP-2026)
Audited and resolved production incident on 16-Sep-2026 where momentary noise tick at 09:22:56 (Spot ₹23,254.50 vs Anchor ₹23,250) triggered an unintended PE Sell without breaking the upper buffer wall (`₹23,250 + 15 = ₹23,265`), followed by a whipsaw drop at 09:24:30 creating an accidental dual-sided strangle:
1. **3-State Hysteresis Deploy Guard (`block_manager.py`)**:
   - `deploy_unified_master_unit` now strictly enforces `regime_buffer`:
     * **Decisive Bullish Breakout** (`Spot >= Anchor + Buffer`): Executes PUT SELL live on broker, arms Call wing in `PENDING`.
     * **Decisive Bearish Breakout** (`Spot <= Anchor - Buffer`): Executes CALL SELL live on broker, arms Put wing in `PENDING`.
     * **Inside Buffer Zone** (`Anchor - Buffer < Spot < Anchor + Buffer`): Sets unit regime to `NEUTRAL` and arms **BOTH** wings in `PENDING`. Zero premature broker orders!
2. **3-State Real-Time Console Banner (`app.py`)**:
   - The Unified Master Console Directional Banner renders 3 explicit states:
     * 🟢 **BULLISH** (`Spot >= Bullish Trigger`): Green banner indicating PE Sell execution.
     * 🔴 **BEARISH** (`Spot <= Bearish Trigger`): Red banner indicating CE Sell execution.
     * 🟡 **NEUTRAL / ARMED** (`Bearish Trigger < Spot < Bullish Trigger`): Amber banner indicating Spot is inside the noise buffer zone, informing the operator that both wings will remain safely armed in `PENDING` until a decisive breakout occurs.
3. **Anti-Strangle Mid-Day Guard (`regime_engine.py`)**:
   - In `evaluate_block_regime()`, if an opposing SELL leg is already `OPEN` in the unit and `is_3pm_or_later == False`, Phase 2 skips deploying the new side (`has_open_opposing` guard).
   - Guarantees that mid-day regime shifts will never create an accidental unhedged or dual-sided strangle while trades are peacefully breathing.
4. **Buffer-Aware Neutral Initialization (`regime_engine.py`)**:
   - When resolving uninitialized or neutral units, `evaluate_block_regime()` requires breaching `Anchor ± Buffer` to transition out of `NEUTRAL`.
5. **Incident Remediation on VPS**:
   - Safely squared off the unintended `23000 PE SELL` and locked profit on `22500 PE HEDGE_BUY` on Zerodha Kite.
   - Retained active hedged Bearish wing: `23800 CE SELL` (-390 Qty) + `24200 CE HEDGE_BUY` (+390 Qty).
6. **Automated Verification**:
   - Verified via `test_v5_buffer_wall_guard.py` covering Bullish breakout, Bearish breakout, Neutral buffer arming, and Anti-Strangle protection (4/4 tests passing: 100% OK).

## 🚀 V5.4 ZERO-CLASH STRIKE SHIELD & FAR-MONTH 500 LIQUIDITY UPGRADE (17-SEP-2026)
Following live market audit on 17-Sep-2026, the Option Selling (OS) engine across Zerodha OS, Kotak Neo, and HDFC Option Selling is upgraded to V5.4:
1. **Zero-Clash Strike Shield (Cross-Engine Deconfliction)**:
   - When hunting candidate strikes, OS engine checks active open strikes across all M-Units (M1, M2, M3) and live broker terminal positions for the same expiry.
   - If candidate strike is already occupied by an M-unit:
     * Call Wing: Automatically shifts +1 step higher (+100 or +500).
     * Put Wing: Automatically shifts -1 step lower (-100 or -500).
   - Guarantees 0% position collisions on broker terminal between directional M-Units and OS multi-day pods.
2. **Dynamic Step Selector (Near Month = 100 | Far Month = 500 Multiples)**:
   - DTE <= 30 days (Near Month): Uses 100-multiples for precise strike resolution.
   - DTE > 30 days (Next / Far Month): Switches to 500-multiples (`23000`, `23500`, `24000`, `24500`, `25000`) where institutional market makers maintain deep liquidity.
   - 500-pt / 1000-pt Hedge ("Helmet"): Hedges also map strictly to 500-multiples.
   - Eliminates illiquid ghost strikes and exchange order rejections.
3. **Limit Order with Protection Buffer (Kotak Neo & HDFC Parity with Zerodha)**:
   - In `kotak_neo_client.py` and `hdfc_client.py`, market orders are converted to limit orders with a 10% protection buffer against live LTP, eliminating NSE error 1041 (`LTP not available for this instrument`).
4. **15:02 IST Auto-Deploy Watchdog**:
   - At 15:02 IST, `evaluate_os_3pm_decision()` inspects locked OS settings (`db.get_os_settings()`).
   - If settings are locked and unit has not yet executed today, automatically deploys qualified decaying wings without requiring manual button clicks.
5. **Blueprint & Specifications**:
   - Detailed blueprint available in `OS_ENGINE_V5.4_UPGRADE_SPEC.md`.

## 🖥️ VPN & IP Settings
- **Whitelisted IP (PERMANENT — NEVER CHANGE)**: `46.224.133.16` (VPN IP)
- **VPS Real IP**: `157.49.182.222` (do NOT use as trading IP)
- **IP Guard**: Engine checks public IP before each cycle. If not `46.224.133.16`, trading pauses + Telegram & ntfy alert.

## 🧱 Lego System Convention
- **lego0_diagnose.py**: VPS diagnostics (logs, status, connections, port checks).
- **lego1_deploy.py**: Laptop-to-VPS SSH deployment script.

## ⚙️ Ports and Services
- **Dashboard Port**: `9007` (PERMANENT — reserved strictly for Zerodha OS. Do not change!)
- **Dashboard URL**: http://46.224.133.16:9007
- **Systemd Services**: `zerodha_engine.service`, `zerodha_dashboard.service`
- **VPS Remote Path**: `/root/BHARAT-SYSTEMS/ZERODHA-OS`
- **⚠️ CRITICAL PORT RULE (DO NOT TOUCH PORT 9004):** Port `9004` is strictly reserved for the operator's stable HDFC option selling system (`hdfc_dashboard.service` and `hdfc_engine.service` located in `/root/BHARAT-SYSTEMS/HDFC-OPTIONSELLING`). Never stop, disable, modify, or host anything on port 9004, and never touch the HDFC system running outside the current Zerodha OS directory!


## 🔑 Broker — ZERODHA KITE CONNECT ONLY
- **Developer Portal**: https://developer.kite.trade/
- **Docs**: https://kite.trade/docs/connect/v3/
- **API Base URL**: `https://api.kite.trade`
- **Active Executor File**: `kite_executor.py` (imported and used directly in core modules)
- **Credentials**: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_CLIENT_CODE`, `KITE_PASSWORD`, `KITE_TOTP_KEY`, and `NTFY_TOPIC`.

### Auth Flow
1. **Automated Headless Login (Morning)**: A requests-based scraper submits Client Code + Password to `kite.zerodha.com/api/login`, retrieves `request_id`, generates TOTP code using `pyotp` and submits it to `/api/twofa` to obtain a session. It then hits `kite.trade/connect/login` to get the redirect `request_token`, which it exchanges for an `access_token`.
2. **Dashboard Redirect Login**: Fallback login button redirects to `kite.login_url()`. Once logged in, the user is redirected back to the Streamlit app which reads the `request_token` from URL parameters and exchanges it.

### Place Order — Request Parameters (Kite Connect SDK)
```python
kite.place_order(
    variety=kite.VARIETY_REGULAR,
    exchange=kite.EXCHANGE_NFO,
    tradingsymbol=trading_symbol,
    transaction_type=transaction_type,  # kite.TRANSACTION_TYPE_BUY / TRANSACTION_TYPE_SELL
    quantity=qty,
    product=kite.PRODUCT_NRML,  # PRODUCT_NRML for multi-day option selling
    order_type=order_type,
    price=price
)
```
**CRITICAL NOTES:**
- **Product type**: F&O overnight positions must be placed using `PRODUCT_NRML` in Zerodha.
- **Market Protection**: To prevent slippage, MARKET orders are converted to LIMIT orders in `kite_executor.py` using live LTP quotes with a maximum 10% buffer.

### Local Instruments Cache
- Instruments are cached daily from `https://api.kite.trade/instruments` to `zerodha_instruments.csv` inside the app directory.
- Expiries and options details are matched locally using pandas filtering on `name == 'NIFTY'` and `exchange == 'NFO'` to resolve contracts quickly.

## 📊 Default Trading Parameters
- **Index**: NIFTY ONLY (HARD RULE — never BANKNIFTY or others)
- **Exchange**: NFO (Zerodha uses NFO for derivatives)
- **Product**: NRML (multi-day holding)
- **Lot Size**: 65 (as of Jun 2026)
- **P&L Refresh Interval**: 30 seconds (1800 seconds fallback)
- **Market Operational Hours**: 09:15 to 15:45 IST (Market active till 3:45 PM)
- **Trading & Re-entry Cutoff**: 15:36 IST (All active entries & same-day re-entries continue till 3:36 PM)
- **EOD Orphan Watchdog & Daily Summary**: 15:36 to 15:45 IST

## 📱 Notifications (Telegram + ntfy)
- Dual alert channel delivery: Telegram alerts duplicate to `https://ntfy.sh/<NTFY_TOPIC>` if configured, serving as a reliable fallback for operators.

## 🔄 Daily Auto-Reset and Re-entry Logic (Option A)
- **Daily Reset Check**: At 09:00 AM IST, the background engine scans all ACTIVE blocks. Any strike that was closed on a previous day (SELL leg is CLOSED) is automatically reset to `PENDING` status along with its linked HEDGE_BUY strike.
- **Auto-Entry Check**: During market trading hours (09:15 to 15:36 IST), the engine monitors `PENDING` SELL strikes. If the Nifty option price drops below its manual `anchor_price` (LTP < anchor_price) and Master Regime aligns, the engine automatically executes it (buys the hedge first, then sells the option).
- **Same-Day Re-entry**: If a strike is closed TODAY (e.g. stopped out during the day), the engine allows it to re-enter today till 15:36 IST if the Nifty option price drops below `anchor_price - reentry_discount_buffer`, provided the hedge strike is still OPEN.
- **Resolved Symbol Lookup**: The engine uses the exact trading symbol resolved from the cache master instead of hand-constructed symbols for live LTP lookup, guaranteeing correct pricing queries.
## 📊 Dashboard Page Architecture (3 Tabs)
- **Page 1: 💰 Nifty Option Selling** (Derivatives Selling Engine)
- **Page 2: 🛢️ MCX Commodities FUT** (Commodities Intraday Engine)
- **Page 3: 📊 Equity & Gold (200 DMA Monitor)** (Holdings & 200 DMA Monitor — `equity_200dma_engine.py`)
  - Compares `LTP` vs `200 DMA` for all Zerodha Equity & Gold holdings (`GOLDBEES`, `SGBs`, Shares).
  - Triggers **Global RED ALERT POPUP BANNER** across ALL 3 pages when any asset's `LTP < 200 DMA`.
  - Detailed system reference in `EQUITY_200DMA_MEMORY.md`.

## 🌐 BHARAT MASTER MULTI-ANCHOR UNIT SYSTEM (V3.0)
- **Autonomous Multi-Anchor Pods (Unit M1, Unit M2, Unit M3...)**:
  - Every block operates as an independent pod with its own `master_anchor_price` (e.g. Unit M1 @ ₹24,000, Unit M2 @ ₹24,500), `regime_buffer` (default: ±15.0 pts), and custom lot allocations.
  - **Simultaneous Independent Regimes**: At Spot ₹24,200:
    - Unit M1 (Anchor ₹24,000) $\implies$ 🟢 **BULLISH** (PE selling active, CE dormant).
    - Unit M2 (Anchor ₹24,500) $\implies$ 🔴 **BEARISH** (CE selling active, PE dormant).
- **Rule 1 — Block-Level Anchor Independence**:
  - The parameter `master_anchor_price` is stored per block in the database.
  - Set strictly via manual user input on each block card or 1-Click `[ ⚡ Lock Spot as M_n Anchor ]`.
  - Zero cross-block interference: modifying Unit M2 has zero impact on Unit M1 or M3.
- **Rule 2 — Decentralized Regime Governance**:
  - `Spot >= Unit Anchor + Buffer`: 🟢 **BULLISH REGIME** $\rightarrow$ Only sell PEs. CE side dormant & covered.
  - `Spot <= Unit Anchor - Buffer`: 🔴 **BEARISH REGIME** $\rightarrow$ Only sell CEs. PE side dormant & covered.
  - **Hysteresis Whipsaw Guard**: Configurable buffer (default `±15.0 pts`) prevents flip-flopping.
- **Rule 3 — Isolated Kill & Flip Protocol**:
  - **Phase 1**: Emergency market-cover of opposing short leg ONLY for the triggered unit.
  - **Phase 2**: Auto-deploy trend-aligned strikes (Buy Hedge $\rightarrow$ Sell Leg) where `LTP < strike_anchor`.
  - Zero contagion across units.
- **Rule 4 — Mathematical Spread Guardrails**:
  - **For CE**: `hedge_strike_price > sell_strike_price` (Hedge must be OTM higher strike).
  - **For PE**: `hedge_strike_price < sell_strike_price` (Hedge must be OTM lower strike).
- **Rule 5 — Universal Operational Timings & 15:25 IST Hard Auto Square-Off**:
  - `15:20 IST`: Hard No-Entry Cutoff across all units (No new entries or re-entries).
  - `15:25 IST`: Mandatory EOD Hard Auto Square-Off closes all open Sells & Hedges (Guaranteed 0 overnight positions).
  - `15:26 IST`: Post-Exit Reconciliation Guard (Verifies 0 open positions on Zerodha API).
  - `15:30 IST`: NSE Market Close & EOD Recap Telegram Summary.

पूरा टेक्निकल ब्लूप्रिंट, डेटाबेस स्कीमा और UI लेआउट देखने के लिए क्लिक करें: 👉 [BHARAT_MASTER_MULTI_ANCHOR_UNIT_V3_BLUEPRINT.md](file:///c:/Users/pc/Desktop/BHARAT-SYSTEMS/ZERODHA%20OS/BHARAT_MASTER_MULTI_ANCHOR_UNIT_V3_BLUEPRINT.md)

---

## 🔍 18-SEP-2026 MORNING TRADES AUDIT & V5.5 OS ARCHITECTURE UPGRADE
Full forensic investigation and hardening across Zerodha OS, Kotak, and HDFC:

### 1. Root Cause of 18-Sep Morning Trades:
- **10 Lots (650 Qty) `22200 PE SELL` @ ₹2.15 (09:15:05 IST)**:
  - Source: External/Kite terminal order (placed via account XM2086 at market open). Not triggered by Python algo engine (engine was sleeping between 09:15:00 and 09:15:09). Strike 22200 was 1,140 pts OTM with ₹2.15 premium (outside ₹150 target).
- **1 Lot (65 Qty) `24500 CE SELL` @ ₹45.40 (09:15:12 IST)**:
  - Source: Leftover test block contamination! During automated test execution on live VPS DB on 17-Sep (`test_v54_os_strike_shield_and_500_step.py`), `test_03` created Block 182 (Unit M1) and Strike 295 (`24500 CE SELL`, 1 lot, `PENDING`). `db.update_block_status` failed to close it because open strikes existed. At market open (Spot ₹23,343 vs Anchor 24,000 = Bearish), `regime_engine` executed this pending test strike. Covered by user 35s later.
- **1 Lot (65 Qty) `23400 PE SELL` @ ₹104.85 (15:02:10 IST)**:
  - Source: OS1 Auto-Deploy at 15:02 IST. Traded 1 lot instead of operator's intended 2 lots because the unit test script `test_05` had overwritten `os_locked_lots = 1` in the live DB on VPS!

### 2. V5.5 Core Invariants Implemented:
1. **Auto-Trade vs Manual Trade Independence**:
   - `db.has_os_auto_traded_today(unit_name)` & `db.mark_os_auto_traded_today(unit_name)` track scheduled 15:02 IST Auto-Pilot executions.
   - The 1-trade-per-day limit applies **ONLY** to the automated 3:02 PM trade.
   - **Manual Operator Execution** (`btn_exec_os_now`) is 100% unrestricted: an operator can execute manual trades anytime, as many times as they want (1, 2, 3... times). Manual executions are never blocked or disabled.
2. **Duplicate Side Overlap Prevention**:
   - When deploying to an OS unit/block, the engine inspects existing open positions.
   - If `has_open_pe` is TRUE, it skips the PE wing to prevent duplicate overlap risk.
   - If `has_open_ce` is TRUE, it skips the CE wing to prevent duplicate overlap risk.
   - If Put is already running, it only evaluates Call (and vice-versa).
3. **Strict Locked Lots Enforcement**:
   - Locked lots (`os_locked_lots = 2`) strictly govern all automatic and manual operations. The engine never defaults or downgrades to 1 lot on its own.
4. **100% Test Isolation**:
   - All unit test suites are rewritten with `test_db_isolated.db` teardown hooks, permanently guaranteeing that tests never touch live production databases (`zerodha_trader.db`, `kotak_trader.db`, `hdfc_trader.db`).

### 3. Operational Window & Cutoff Exemption Rule (Permanent V5.6 Fix)
- **Problem**: `ACTIVE_TRADING_CUTOFF_TIME = "15:13"` in `block_manager.py:execute_strike()` was originally designed for intraday directional M-Units (M1, M2...) to prevent midday churn re-entries.
- **Root Cause of Manual Deploy Block**: In sister brokers (like HDFC), when an operator attempted manual execution or auto-deployment of an OS unit between 15:13 and 15:30 IST, the intraday cutoff blocked `execute_strike()` with `Execution BLOCKED: 15:13 IST Cutoff reached.` Furthermore, `deploy_os_wing()` masked the error as a note, leaving strikes stuck in `PENDING` without placing broker orders.
- **Architectural Resolution across all 3 platforms**:
  1. **OS Unit Exemption**: `is_os = bool(unit_name and unit_name.strip().upper().startswith("OS"))`. OS units and manual operator executions (`ignore_cooldown=True`) are explicitly exempt from the 15:13 M-unit cutoff and allowed up to 15:30 market close.
  2. **Clean Error Propagation**: `deploy_os_wing()` and `deploy_os_unit()` return `ok: False` on execution failure so the operator sees the exact broker error in Streamlit instead of silent failure.
  3. **Stale PENDING Deduplication**: Before adding strikes for a new deployment, any stale unexecuted `PENDING` strikes in the block are purged to prevent duplicate ghost strikes.

---

## 🏛️ V6.0 M-UNITS (M1–M4) ASYMMETRIC EXECUTION & AUTO-HUNTER ARCHITECTURE (24-SEP-2026)

### 1. Asymmetric Entry Rule (Midday Opposing Blocker Permanent Removal)
- **Core Principle**: If Spot crosses Master Anchor (e.g. falls below 23,350 into Bearish territory), the trend-aligned side (**CALL Selling**) is **INITIATED IMMEDIATELY** during morning or any 5-minute decision loop.
- **No Midday Blocking by Old Positions**: An existing open Put leg from a previous session must **NEVER** block Call initiation!
  - The running Put leg is protected by its autonomous **25% Stop-Loss**. If the market dumps violently, the Put leg's SL fires automatically.
  - Midday cutting of existing legs is forbidden to prevent whipsaws.
  - Zero Simultaneous Initiation from scratch: Both Call and Put are never initiated together from a neutral state.
- **3:00 PM (15:00 IST) Wrong-Side Clean Cut**:
  - At 15:00 IST, the engine evaluates the session-closing regime.
  - The opposing "Wrong Side" leg (e.g. Put in a Bearish close) is squared off on the broker terminal.
  - The qualified trend-aligned leg (e.g. Call spread) is held overnight for multi-day theta decay.
  - Orphan hedges are squared off at 15:25 IST.

### 2. M-Units Express Auto-Hunter (Parity with OS)
- **Automatic Option Chain Scanning**:
  - Instead of manual strike typing, M-Units scan live option chain for nearby ATM/OTM strikes based on Spot and Master Anchor.
  - Auto-calculates 500-pt Hedge Helmet (+500 for CE, -500 for PE).
  - Displays transparent preview cards with live LTP, Hedge LTP, and 25% SL trigger price.
  - Provides dual mode: 1-Click Auto-Lock vs Manual Strike Override.

### 3. Stop-Loss Immutable Rule (25% on Actual Sold Fill Price)
$$\text{SL Trigger Price} = \text{Actual Broker Fill Price} \times 1.25 \quad (+25.0\%)$$
- Locked permanently at entry fill. Never floats or recalculates on subsequent days.

### 4. Unified Anchor Cockpit
- Single master anchor per pod (`M1`, `M2`...).
- Prominent Executive Cockpit Banner at top of M-Units tab showing Anchor, Spot LTP, Regime, Active Leg, and 1-Click `[ ✏️ Edit Anchor ]` button. All scattered redundant anchor inputs removed.

### 5. Odd vs Even Strike Specialization
- **OS Units**: ODD 100-Multiples (23100, 23300, 23500...) @ ~₹150 target premium.
- **M-Units**: EVEN 100-Multiples & 500-Steps (23000, 23200, 23400, 23500, 24000...) nearby ATM/OTM.

---

### 6. Architectural Behavioral Rules Under Spot Drop (e.g. Spot = 23,112 vs Anchor = 23,200)
1. **Call Trade Auto-Trigger**:
   - If an M-Unit block has Put open and Call in `PENDING`, when Spot drops below Anchor ($23,112 < 23,200$), the engine evaluates regime as `BEARISH`.
   - In `evaluate_master_anchor_regime()`, Phase 2 auto-deploy **immediately fires the trend-aligned Call spread** (500-pt Hedge first $\rightarrow$ Sell second).
2. **Put Side Midday Invariant (Peaceful Hold)**:
   - Midday cutting of running trades is **FORBIDDEN** to prevent whipsaws.
   - The Put spread is **NOT cut midday**. It is held peacefully until **15:00 IST (3:00 PM)** EOD audit, where Phase 1 squares off the opposing wrong-side leg.
3. **Autonomous 25% Stop-Loss (Runs Every 30 Seconds)**:
   - Evaluated on **every 30-second P&L cycle** in `pnl_engine.py` (does not wait for 5 minutes or 3:00 PM).
   - If the sold Put premium rises by $+25.0\%$ above actual broker fill price ($\text{Fill} \times 1.25$), the engine **immediately buys to cover the sold leg on the broker terminal**.
   - A 30% loss is never allowed because the 25% threshold triggers and fills first.

---

### 7. V6.1 Just-In-Time (JIT) Dynamic Auto-Hunter & Zero-Buffer Hysteresis Alignment
1. **Zero Hysteresis Lag (`regime_buffer = 0.0`)**:
   - For V6.1 M-Units, `regime_buffer` is set to `0.0`.
   - $\text{Spot} \ge \text{Anchor} \implies \text{BULLISH}$ (PUT Selling Qualified, CALL Standby).
   - $\text{Spot} < \text{Anchor} \implies \text{BEARISH}$ (CALL Selling Qualified, PUT Standby).
   - 100% eliminates the 15-point disconnect between UI and backend execution.
2. **Just-In-Time (JIT) Dynamic Auto-Hunter on Trigger**:
   - Pods are armed with **User Anchor (₹23,200)**, **Expiry**, and **Target Premium (~₹200)**.
   - If trigger arrives days later (e.g. Day 10), the engine does **NOT** execute stale pre-drafted strikes whose premium has decayed to ₹40.
   - At the exact moment of trigger in Phase 2 auto-deploy:
     - Hunter queries live option chain for the current EVEN 100-multiple closest to ~₹200.
     - Auto-pairs 500-pt Hedge Helmet (+500 CE, -500 PE).
     - Locks strict 25% SL on actual entry fill.
     - Executes Buy Hedge first $\rightarrow$ Sell Leg second.
3. **Anti-Duplicate Stacking Invariant**:
   - `has_active_open` check: If an active leg on that side is already `OPEN`, auto-deploy is strictly bypassed.
   - Never stacks a new trade on top of an already running position.
4. **Post-Execution Immutability**:
   - Once filled on broker (`status == 'OPEN'`), strikes are 100% locked.
   - Governed purely by autonomous 25% SL and 15:00 IST session clean-cut.

---

### 8. V6.2 True 5-Minute Stay Confirmation Timer, Single-Direction Sanctity Guard & Pure Even Strikes (29-SEP-2026)

#### 1. Forensic Audit (29-Sep-2026 Morning Trade Analysis)
- **What Happened**:
  - M1 Block 188 was initiated at **09:24:27 IST** (Anchor: 22,660, Spot: 22,666.90 $\implies$ Bullish $\implies$ executed `22500 PE SELL` @ ₹210.05).
  - Spot briefly fell below 22,645 (Anchor - 15pt buffer) at **09:27:46 IST**.
  - In legacy code:
    1. Regime flipped to `BEARISH` on a single 30s tick without waiting for a 5-minute sustained stay.
    2. `regime_engine.py` refrained from deploying CE because PE was open, BUT `pnl_engine.py:857`'s generic `PENDING-ENTRY-CHECK` executed `23200 CE SELL` @ 09:27:50 IST, turning M1 into a dual strangle midday.
    3. `22500 PE` was selected because `block_manager.py:2636` had `| (subset["strike"] % 500 == 0)` in `even_pool`, causing odd 500-multiples (`22500 // 100 = 225`) to leak into M-Unit selling.

#### 2. Architecture Repairs Implemented (Lego System Protocol)

- **Brick 1: True 5-Minute Stay Confirmation Timer (`regime_engine.py`)**:
  - Added stay tracking in `evaluate_block_regime()` using `breakout_ts_bearish_{block_id}` and `breakout_ts_bullish_{block_id}` with `regime_stay_duration_sec = 300` (5 minutes).
  - Spot breaching buffer stamps breakout start timestamp; regime only transitions to Bearish/Bullish if Spot sustains beyond buffer for $\ge 300$ seconds continuously.
  - If Spot bounces back within the buffer before 300s elapses, the breakout timer immediately resets.

- **Brick 2: Single-Direction Sanctity Guard (`pnl_engine.py`)**:
  - Added check in `PENDING-ENTRY-CHECK` before placing any opposite short leg:
    If an M-Unit already has an opposing short leg in `OPEN` status before 15:00 IST, entry of the second opposite short leg is strictly blocked.
  - Midday churn is prevented. The existing leg stays protected by its autonomous 25% Stop-Loss sentinel.
  - At 15:00 IST, `execute_3pm_master_anchor_decision()` evaluates the regime and cleanly squares off the wrong-side leg.

- **Brick 3: Pure Even 100-Multiples Selection (`block_manager.py`)**:
  - Removed `| (subset["strike"] % 500 == 0)` from `even_pool` in `block_manager.py`.
  - M-Units now strictly select `(strike // 100) % 2 == 0` (e.g. 22400, 22600, 22800, 23000, 23200).
  - Odd strikes (e.g. 22500, 22700, 23500) are reserved strictly for OS units.

#### 3. Verification & Deployment Status
- Local unit test suite [test_5min_stay_and_even_strikes.py](file:///c:/Users/pc/Desktop/BHARAT-SYSTEMS/ZERODHA%20OS/test_5min_stay_and_even_strikes.py): 3/3 tests PASSED (100%).
- All 15 local tests across 4 test suites passed.
- VPS upload verified and executed directly on VPS (`46.224.133.16`): ALL 3 TESTS PASSED.
- Services `zerodha_engine.service` and `zerodha_dashboard.service` restarted and active.
- Git repository synced with origin.

---

### 9. V6.3 JIT Dynamic Auto-Hunter, Minimum Floor Guard & 14:55 Entry Freeze (30-SEP-2026)

#### 1. Forensic Audit (30-Sep-2026 14:57 CE Execution Incident)
- **The Observation**:
  - At **14:57:36 IST** on 30-Sep-2026, Unit M1 executed a live Call sell:
    - **BUY 260 qty `23700 CE`** @ ₹36.65 (Hedge)
    - **SELL 260 qty `23200 CE`** @ ₹118.60 (Net Credit: ₹81.95)
  - The operator had configured M1 with a **Target Premium of ~₹200**.
  - Selling at ₹118.60 represented a 41% premium decay from the intended ₹200 target, and entering just 3 minutes before the 3:00 PM session close violated intraday trading intent.
- **Forensic Root Causes**:
  1. **Stale Pre-Drafted Strikes in SQLite**:
     - Strike `23200 CE` was drafted on **29-Sep at 09:24:27 AM** when Nifty Spot was 22,666 and premium was ₹163.20 (stored in `anchor_price = 163.20`).
     - Over 30 hours of market oscillation and theta decay, the premium fell from ₹163.20 to ₹118.60.
     - While the Streamlit UI (`app.py`) possessed an `inspect_m_unit_candidates()` auto-hunter at setup time, the background daemon loops (`pnl_engine.py` and `regime_engine.py`) had **no dynamic hunter integration**.
     - `pnl_engine.py:857`'s generic loop simply checked `ltp <= anchor_price` ($118.75 \le 163.20$), deemed it qualified, and blindly executed the stale strike without re-evaluating live market option chain candidates.
  2. **Timing Disconnect (`14:57` Decision vs `15:13` Active Cutoff)**:
     - `MASTER_DECISION_TIME` was set to `14:57`, but `ACTIVE_TRADING_CUTOFF_TIME` was `15:13`.
     - When the 14:57 3:00 PM Continuation Decision cleanly closed the losing Put leg (`22500 PE`), the unit was left with zero open legs.
     - Because `14:57 < 15:13`, the normal 30-second cycle was still active. It saw zero open opposing legs, saw the pending `23200 CE` strike, and immediately fired the trade at 14:57:36 IST.
  3. **Silent Crash in Regime Stay Duration (`regime_engine.py:171`)**:
     - `float(db.get("regime_stay_duration_sec", "300"))` raised a `ValueError: could not convert string to float: ''` whenever SQLite returned an empty string, breaking Phase 2 auto-deploy fallback logic.

#### 2. Architectural Repairs Implemented (Lego System Protocol)

- **Brick 1: JIT Dynamic Auto-Hunter (`hunt_and_execute_jit_m_strike` in `block_manager.py`)**:
  - Whenever an M-Unit pending leg triggers (either in `pnl_engine.py` generic cycle or `regime_engine.py` Phase 2):
    1. The engine reads the unit's configured `target_premium` (defaults to ₹200.0 if not specified).
    2. Dynamically queries Kite live quotes for all available EVEN 100-multiple strikes (`(strike // 100) % 2 == 0`).
    3. Identifies the strike whose live LTP is closest to `target_premium`.
    4. Automatically pairs the corresponding 500-pt Hedge strike (+500 for CE, -500 for PE).
    5. Atomically updates the pending strike record and hedge record in SQLite via `db.update_strike_details()`.
    6. Executes the trade margin-safely: **Buy Hedge First $\rightarrow$ Sell Short Leg Second**.

- **Brick 2: Minimum Premium Floor Guard (`block_manager.py`)**:
  - Hard mathematical floor applied to all M-Unit entries:
    $$\text{Floor} = \max\left(100.0, \, \text{target\_premium} \times 0.70\right)$$
  - For a target of ₹200, any candidate trading below **₹140.00** is strictly rejected as decayed junk.
  - If no candidate satisfies the floor, execution is skipped and a warning is logged (`⚠️ NO TRADE QUALIFIED`).

- **Brick 3: 14:55 / Post-3PM Entry Freeze (`pnl_engine.py` & `regime_engine.py`)**:
  - Added strict entry freeze gatekeeper:
    ```python
    is_3pm_frozen = (db.get("last_3pm_decision_date") == today_str) or (now_time_str >= "14:55")
    ```
  - Fresh pending M-unit entries are strictly blocked once the clock reaches 14:55 IST or after the 3:00 PM continuation decision has executed for the day.

- **Brick 4: Safe Empty String Conversion (`regime_engine.py`)**:
  - Replaced `float(db.get("regime_stay_duration_sec", "300"))` with:
    ```python
    stay_sec = float(db.get("regime_stay_duration_sec") or 300)
    ```
  - Completely immune to empty string returns from SQLite.

- **Brick 5: Atomic Multi-Field Strike Update (`db.py`)**:
  - Implemented `update_strike_details(strike_id, strike_price, anchor_price, sl_price, sl_pct, lots)` ensuring that strike price, anchor price, and stop-loss levels are updated in a single atomic transaction.

#### 3. Verification & Deployment Status
- **Test Suite**: [`test_jit_m_hunter_and_floor.py`](file:///c:/Users/pc/Desktop/BHARAT-SYSTEMS/ZERODHA%20OS/test_jit_m_hunter_and_floor.py)
  - `test_01_jit_dynamic_strike_replacement_at_execution`: **PASSED** (Replaces stale 23200 with fresh 23000 @ ₹182.50 ~ ₹200 target).
  - `test_02_minimum_floor_guard_rejects_decayed_junk`: **PASSED** (Rejects candidate @ ₹118.60 below ₹140.00 floor).
  - `test_03_post_3pm_and_1455_entry_freeze`: **PASSED** (Blocks execution at 14:57 and post-3PM decision).
- **Remote Host Verification**:
  - Deployed to VPS (`46.224.133.16`).
  - Unit tests executed on VPS: **100% PASSED**.
  - All 15 core files verified **0 bytes diff** against production VPS.
  - `zerodha_engine.service` (PID 709057) and `zerodha_dashboard.service` (PID 709058, Port 9007) **active and running**.
  - Git commit `b25468d` pushed to GitHub `origin/master`.

---

### 10. Forensic Audit & Product Remediation Specification: Weekly ST-2H Cockpit (02-Oct-2026)
1. **Reported Symptoms**:
   - Operator noted "in Zerodha the system is not bad but there are also some issues that is creating confusion."
   - Preview Option 1 ("🎯 Preview Strike Selection with this Strategy") in Row 2.5 looks dummy.
   - Strike selection for Next Week searches Current Week.
2. **Root Causes & Architectural Repairs Implemented (02-Oct-2026)**:
   - **Brick 1 (In-Place Row 2.5 Strategy Preview Card)**: Directly displays target expiry, mode, Short Leg strike & LTP, Hedge Leg strike & LTP, Net credit per share and lot, and Moat Rule validation in real-time.
   - **Brick 2 (Row 5 Synchronization)**: Button 2 now passes active strategy parameters (`expiry_mode`, `target_expiry`, `min_spot_buffer`, `st_clearance`, `st_value`, `spot_val`).
   - **Brick 3 (Expiry Tagging Fix)**: Replaced misleading ternary with dynamic week classification (`NEXT WEEK (DIRECT)`, `CURRENT WEEK`, `FALLBACK TO NEXT WEEK`).

---

### 11. Product Upgradation: Weekly ST-2H Cockpit V7.5 Master Edition (02-Oct-2026)
1. **Scope & Motivation**:
   - Operator required prominent **V7.5** version branding in Cockpit Header (`[ 🚀 V7.5 MASTER EDITION ]`) and Main Navigation (`⚡ Weekly ST-2H Cockpit (W1 — V7.5)`).
   - Eliminated operator confusion from duplicate preview buttons across different rows on the screen.
2. **Defects Remediated**:
   - **Elimination of Duplicate Preview Button**: Completely removed `btn_w_preview_hunter` and duplicate preview card from Row 5. Row 5 is now dedicated exclusively to `🛠️ Pulse Engine Diagnostic & Manual Force-Trigger Tools`.
   - **Unified Single Authoritative Console**: Created `_render_strike_preview_card` in Row 2.5 for both Draft Mode and Locked Mode (with `🎯 Refresh Live Strike Scan (Armed Strategy)` button).
3. **Invariants**:
   - Never add a strike preview button to Row 5 or anywhere outside Row 2.5.
   - Always display `[ 🚀 V7.5 MASTER EDITION ]` branding in the cockpit header.

---

### 12. Forensic Audit & Product Upgradation: V8.2 Institutional Mirror & M1 Execution (14-Oct-2026)
1. **V8.2 Institutional Parity ("Chhoti Bahan" Edition)**:
   - Full integration of brother's release bundle (`ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip`).
   - Added W1 Weekly ST 2-Hour Autonomous Engine (`weekly_st_engine.py`, `ui_weekly_st.py`) with 3 pulses/day (`11:15`, `13:15`, `15:10 IST`) and Asymmetric Dual-Expiry Hunter.
   - Fixed M-Units LTP polling with continuous live streaming via `terminal_backend.py` + `block_manager.py`.
   - Dedicated Sister VPS: `5.75.250.104` (Port `9007`).
2. **M1 Execution Failure Forensic Root-Cause**:
   - **Primary Cause**: Arming via `"Arm Both Wings in PENDING (Standby)"` safely sets strike status to `PENDING` without placing orders on Zerodha Kite.
   - **Secondary Cause**: In `execute_strike()`, a micro-move check `if current_ltp >= anchor_price + 2.0` blocked execution whenever option price fluctuated higher than stale anchor.
   - **Resolution**:
     * Modified `execute_strike()` and `execute_block()` to auto-sync anchor price to `fresh_ltp` right before execution when deploying from `PENDING` or explicit manual trigger (`ignore_cooldown=True`).
     * Corrected Block 81 Master Anchor from `23,650.00` (1,000 pt typo) to `22,650.00`.
     * Live Spot (`22,612`) < Anchor (`22,650`) -> `BEARISH` Regime confirmed.
     * Deployed and verified on VPS `5.75.250.104:9007`.
3. **Critical Outbound IPv6 Broker Rejection Bug & Resolution**:
   - **Root Cause**: HostAsia VPS dual-stack routed HTTPS requests to `api.kite.trade` via IPv6 (`2a01:4f8:c014:6479::1`).
   - **Broker Rejection**: Kite Connect API only whitelisted IPv4 `5.75.250.104`, throwing: `IP (2a01:4f8:c014:6479::1) is not allowed to place orders for this app`.
   - **Resolution**:
     * Disabled IPv6 permanently via sysctl (`net.ipv6.conf.all.disable_ipv6 = 1`) in `/etc/sysctl.conf`.
     * Added `urllib3.util.connection.HAS_IPV6 = False` in `kite_executor.py`.
   - **Broker Ground Truth Verified**:
     * Weekly ST Engine: `NIFTY26OCT22250PE` (-65 qty) / `NIFTY26OCT21750PE` (+65 qty) -> **STATUS: COMPLETE**.
     * M1 Unit: `NIFTY26NOV23200CE` (-325 qty) / `NIFTY26NOV23700CE` (+325 qty) -> **STATUS: COMPLETE**.
     * Total Active Broker Legs: 4 (Both systems live with protective armor).





---

## 🛒 04-NOV-2026: BHARAT OPTION BUYING ENGINE (NSL v6.1 — NON-MONTHLY BREAKOUT & CHHOTI BAHAN INVARIANTS)

### 📋 1. Architectural Genesis & Coexistence Mandate
- **Source Artifact:** Brother's Zip package `ZERODHA_OPTION_BUYING_PACKAGE` (`NSL v6.0`).
- **Target Desk:** Chhoti Bahan / Sister's Trading Desk on Zerodha (`XK7125`).
- **Core Dilemma:** Existing Option Selling setups (`M1`, `M2`, `M3`) sell **Monthly Expiry** contracts. Running Monthly Option Buying on the same broker account introduces orderbook clash, margin competition, and operator confusion.
- **Master User Rule (Non-Monthly Invariant):**
  - **STRICTLY AVOID MONTHLY EXPIRY DATES.**
  - Target weekly expiries ~3 to 4 weeks forward (approx 21-28 days).
  - If the 4th week is the Monthly Expiry, **cascade to the 3rd Week** (approx 14-21 days forward) for maximum liquidity.
- **Strike Selection Rule (Modulo 100 Invariant):**
  - Far-dated weekly 50-ending strikes (`23750, 23850`) suffer from nil/thin liquidity and extreme bid-ask slippage.
  - **STRICTLY EVEN 100 STRIKES ONLY** (`strike % 100 == 0`: `23600, 23700, 23800...`).
- **Position Sizing:**
  - Strictly **1 Lot** (`65 Qty`) to start. Capital risk capped at approx ₹10,400-₹13,000.
- **Long-Only Coexistence Shield:**
  - `get_open_buying_position()` filters `quantity > 0` AND matching token. Any short position (`quantity < 0`) is 100% invisible and untouchable.
  - Tag: `NSLBUY`.
  - Database: Private `zerodha_buying.db` (isolated from `zerodha_trader.db`).
- **UI Architecture Decision:**
  - Dedicated standalone page/dashboard rather than cramming into Port 9007 to eliminate cognitive clutter ("bhashan") and prevent cross-app state corruption.
