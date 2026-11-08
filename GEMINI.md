# 🏛️ GEMINI.md — BHARAT ZERODHA OPTION SELLING ENGINE
> **Master Operating Context, System Behavior Protocol & Architectural Invariants**  
> *Target System: Zerodha Kite Option Selling App (Bharat Systems)*  
> *Last Updated: 08-Oct-2026*

---

## ⚡ SYSTEM BEHAVIOR & OUTPUT PROTOCOL

### 0. MANDATORY PRE-TASK RESEARCH & MEMORY INVARIANT (GURJEET MAMU'S LAW)
> 🚨 **PERMANENT SYSTEM INVARIANT — ZERO EXCEPTION PROTOCOL:**  
> Before executing, proposing, or answering ANY task or question, the agent MUST forcefully read and inspect `GEMINI.md` and `memory.md`.
- **Zero Improvisation / Zero Hallucination**: Never guess, assume, or invent rules from memory.
- **Strict Ground Truth Verification**: Every operational logic, buffer rule, execution trigger, and invariant must be cross-verified against `GEMINI.md` and `memory.md` first.
- **Discrepancy Guard**: If a user request or newly encountered state differs from established memory invariants, the agent must explicitly cite the memory rule and ask/confirm before proceeding.
- **Lego Protocol Gate**: Always diagnose first, present the blueprint, obtain explicit approval, and then execute via the single-brick Lego Protocol.

### 0b. PERMANENT NO-DESKTOP-FILES & IN-CHAT WHATSAPP PROTOCOL (CHHOTI BAHAN'S RULE)
> 🚨 **PERMANENT USER INVARIANT — NEVER WRITE FILES TO USER'S DESKTOP:**  
> - **NEVER** save or dump `.txt`, `.html`, or report files to the user's Desktop (`C:\Users\Dell\Desktop\`) or local computer screen. The user cannot track them there.
> - **ALWAYS** deliver all answers, audit reports, trade status, and explanations directly **RIGHT HERE IN THE CHAT WINDOW**.
> - Every answer must contain a clean, formatted, full-detail **WhatsApp Copy-Paste Block** (` ```text `) so the user can 1-click copy and send it directly to her brother.

### 1. CORE OPERATING PRINCIPLE (CLAUDE-STYLE PARITY)
- **Tone**: Institutional, hyper-concise, technical, and deterministic.
- **Zero Fluff**: Never include introductory filler (e.g., "Sure, I can help with that", "Here is the summary"), polite sign-offs, or generic disclaimers unless explicitly asked.
- **Direct to Point**: Always start the response directly with the deliverable, heading, or data table.

### 2. STRUCTURAL & VISUAL DESIGN
- **Structure-First**: Deliver logic, setups, and workflows using Markdown tables, clean code blocks, and structured lists.
- **Tables for Multi-Variable Logic**: Any comparison, mapping, matrix, or parameter definition must be laid out in a high-density, legible Markdown table.
- **Monospace Precision**: Wrap all strikes, tickers, numbers, code variables, timestamps, and parameters in inline code tags (e.g., `22650`, `V8.2`, `M1`, `W1`).
- **Clear Hierarchies**: Use H2 (`##`) and H3 (`###`) headings to strictly separate:
  - Architecture / Logic
  - Execution Parameters / Math
  - Edge Cases / Overlap Checks
  - Deployment / Step-by-Step Plans

### 3. QUANTITATIVE & SYSTEM LOGIC RULES
- **Deterministic Math**: Always make mathematical bounds explicit (e.g., Modulo operations, disjoint sets, parity checks).
- **Disjoint & Overlap Checks**: When designing multiple systems or order streams, explicitly verify and document collision risk (e.g., `0.00%` Mathematical Overlap).
- **Separation of Concerns**: Keep core algorithm logic, broker order-routing rules, and execution engines isolated and clearly compartmentalized.

### 4. CODING & DEPLOYMENT PROTOCOL
- **Production-Grade**: Code snippets must be modular, robust, syntax-error-free, and directly production/VPS ready.
- **Inline Documentation**: Provide minimal, meaningful comments inside code rather than long explanatory text blocks below the code.
- **Operational Cleanliness**: All configuration setups, environment variables, and file structures must be shown as clean directory trees or key-value tables.
- **Always Maintain GEMINI.md**: Always preserve and maintain `GEMINI.md` as the primary repository anchor and system ground truth.

---

## 📌 1. SYSTEM OVERVIEW & ENVIRONMENT CONFIGURATION

| Parameter | Specification | Notes |
|---|---|---|
| **Local Workspace** | `c:\Users\pc\Desktop\BHARAT-SYSTEMS\ZERODHA OS` | Windows Dev Environment |
| **VPS Remote Directory** | `/root/BHARAT-SYSTEMS/ZERODHA-OS` | Ubuntu 22.04 LTS (Hostasia) |
| **Whitelisted Trading IP** | **`46.224.133.16`** | ⚠️ **PERMANENT — NEVER MODIFY.** VPN Public IP required by Broker API |
| **VPS SSH Host / User** | `46.224.133.16` / `root` | Credentials stored in untracked `secrets.txt` |
| **Web Dashboard Port** | **`9007`** | `http://46.224.133.16:9007` (Streamlit UI) |
| **Engine Systemd Service** | `zerodha_engine.service` | Autonomous background trading loop (`main.py`) |
| **Dashboard Systemd Service**| `zerodha_dashboard.service` | Web UI process (`app.py` on Port `9007`) |
| **Primary SQLite Database** | `zerodha_trader.db` | Local state cache & settings |
| **Broker Client** | Zerodha Kite Connect REST API | `kite_executor.py` adapter |

---

## 🗺️ 2. PERMANENT VPS PORT & SERVICE MAP (NEVER GUESS)

| System Name | Directory Path | Dashboard Port | Systemd Service Names |
|---|---|---|---|
| **NSL** | `/root/BHARAT-SYSTEMS/NSL/` | **Port 9001** | `nsl_dashboard.service`, `nsl_engine.service` |
| **BNSL** | `/root/BHARAT-SYSTEMS/BNSL/` | **Port 9002** | `bnsl_dashboard.service`, `bnsl_engine.service` |
| **Kotak OS** | `/root/BHARAT-SYSTEMS/KOTAK-OPTIONSELLING/` | **Port 9003** | `kotak_dashboard.service`, `kotak_engine.service` |
| **HDFC OS** | `/root/BHARAT-SYSTEMS/HDFC-OPTIONSELLING/` | **Port 9004** | `hdfc_dashboard.service`, `hdfc_engine.service` |
| **Futures** | `/root/BHARAT-SYSTEMS/FUTURES/` | **Port 9005** | `futures_dashboard.service`, `futures_engine.service` |
| **BTC Theta** | `/root/BHARAT-SYSTEMS/BTC-THETADECAY/` | **Port 9006** | `btc_dashboard.service`, `btc_engine.service` |
| **ZERODHA OS** | `/root/BHARAT-SYSTEMS/ZERODHA-OS/` | **Port 9007** | **`zerodha_dashboard.service`**, **`zerodha_engine.service`** |
| **ZERODHA BUYING** | `/root/BHARAT-SYSTEMS/ZERODHA-OPTION-BUYING/` | **Port 9008** | **`zerodha_buying_dashboard.service`**, **`zerodha_buying_engine.service`** |
| **Zerodha AVI** | `/root/BHARAT-SYSTEMS/ZERODHA-AVI-OPTION-SELLING/` | **Port 9011** | `zerodha_avi_dashboard.service`, `zerodha_avi_engine.service` |

> ⚠️ **HARD RULE:** Never hallucinate or confuse ports. Zerodha OS Dashboard is permanently **Port 9007**.

---

## 🎯 3. TRADING ARCHITECTURE RULES (M-UNITS vs OS SYSTEM vs W1)

| Feature | M-Unit Systems (`M1`, `M2`, `M3`) | OS System (`OS1`–`OS5`) — V8.1 | Weekly ST Engine (`W1`) — V8.2 |
|---|---|---|---|
| **Strike Series** | **`00`-Ending Series** (`22600, 22700, 22800...`) | **`50`-Ending Series** (`22550, 22650, 22750...`) | Dynamic 50-strike grid based on Regime |
| **Modulo Filter** | `strike % 100 == 0` | `strike % 100 == 50` | `min_prem <= LTP <= max_prem` (~₹80 target) |
| **Protective Armor** | Integrated Hedge Buy | Helmet Hedge (`sell_strike ± hedge_dist`) | Synthetic Protective Armor (`±500 pts`) |
| **Mathematical Overlap** | **`0.00%`** Collision with OS | **`0.00%`** Collision with M-Units | Disjoint execution table (`weekly_st_positions`) |
| **Execution Cadence** | Continuous (30s P&L monitor) | Continuous (30s monitor) | **3 Pulses/Day**: `11:15`, `13:15`, `15:10 IST` (+ Mon) |

### Weekly ST Engine (W1) — V8.2 Asymmetric Dual-Expiry Hunter & Volatility Cascade
1. **Regime Identification**: SuperTrend (8, 3) evaluated on native 2-Hour Nifty candles.
   - Bullish $\implies$ Deploy **Bull Put Spread** (Sell PE + Buy PE hedge at `-500 pts`).
   - Bearish $\implies$ Deploy **Bear Call Spread** (Sell CE + Buy CE hedge at `+500 pts`).
2. **Current Week Scan (`Step 1`)**:
   - Strictly enforces SuperTrend Moat ($ST \pm 50\text{ pt}$ buffer) AND Spot buffer ($Spot \pm 150\text{ pt}$).
   - Looks for liquid strike paying ₹65–₹115 (sweet spot ~₹80).
3. **Next Week Asymmetric Hunter (`Step 2`)**:
   - When market experiences steep intra-week trending moves, current week safe strikes decay below ₹65.
   - Engine shifts to **Next Week Expiry** (e.g. `19-OCT-2026`).
   - **Crucial Rule**: Next week strike selection **bypasses current-week SuperTrend moat line** and enforces **Spot OTM Clearance** ($Spot \pm 150\text{ pt}$ buffer).
   - This prevents false-trapping behind a distant 2H SuperTrend barrier and captures optimal **₹80 natural theta decay**.
4. **Deep Volatility Cascade (`Step 2b`)**:
   - If severe market exhaustion decays next week strikes below ₹65, engine cascades to **Monthly Expiry** (`27-OCT-2026`).

---

## 🛡️ 4. HARD INVARIANTS & WHITE GLASS BROKER GROUND TRUTH

1. **Broker is Single Source of Truth**: SQLite DB (`zerodha_trader.db`) is a mirror. Execution decisions must always verify broker ground truth via broker REST API.
2. **Three-State Broker Position Reconciliation (`SHORT` / `FLAT` / `UNKNOWN`)**:
   - `SHORT`: Broker holds confirmed net short.
   - `FLAT`: Broker confirmed 0 position.
   - `UNKNOWN`: Broker connection lost, API timeout, or unparseable state.
   - **FAIL-SAFE**: On `UNKNOWN`, the engine **does NOTHING** — no ghost-closes, no entries, no flips.
3. **Broker Ground Truth Methods Across Sister Platforms**:
   - **Zerodha Kite**: `kite.positions()` $\rightarrow$ verify `p['net']` for short token and qty.
   - **Kotak Neo**: `client.positions()` $\rightarrow$ check net open F&O derivative contracts.
   - **HDFC Sky**: `hdfc_executor.get_positions()` $\rightarrow$ net intraday F&O derivatives.
     - ⚠️ **CRITICAL INVARIANT:** Never call `hdfc_executor.get_holdings()` for F&O positions; holdings only return Demat equity assets. Calling `ensure_logged_in()` is mandatory before inspecting login flags.
4. **Verify-Then-Close Execution**:
   - Cover orders fire **only** when broker actually holds the short leg.
   - If broker is already `FLAT`, marks DB closed with zero market orders placed.
   - After covering, verifies `FLAT` before allowing any flip to open.
5. **Strict One-OPEN Guard**:
   - Enforces that only one active weekly spread can ever exist; prevents duplicate stacking.
6. **Margin Protection Invariant**:
   - Entry: **Buy Hedge FIRST** $\rightarrow$ **Sell Short SECOND**.
   - Exit: **Buy-to-Cover Short FIRST** $\rightarrow$ **Sell Hedge SECOND**.

---

## 🚀 5. GURJAS'S LEGO PROTOCOL & DUAL-SERVICE DEPLOYMENT PLAYBOOK

```
[1. DIAGNOSE] ➔ [2. BLUEPRINT] ➔ [3. APPROVAL] ➔ [4. SINGLE-BRICK CODE] ➔ [5. DUAL-SERVICE DEPLOY] ➔ [6. VERIFY]
```

1. **Dual-Service Deployment Invariant**:
   - When deploying to VPS, ALWAYS restart BOTH:
     1. Engine Service: `zerodha_engine.service`
     2. Dashboard Service: `zerodha_dashboard.service` (Port `9007`)
   - Clean Python bytecode cache (`__pycache__`) before restarting so Streamlit does not serve stale RAM cache.
2. **Standard Deployment Sequence**:
   ```powershell
   python lego1_deploy.py
   ```
3. **VPS Diagnosis Sequence**:
   ```powershell
   python lego0_diagnose.py
   ```

---

## 📊 6. TRI-BROKER PARITY AUDIT (08-OCT-2026 POST-MORTEM)

| System | Pre-Fix Status | Root Cause | Resolution | Post-Fix Live Hunter Output |
|---|---|---|---|---|
| **Zerodha OS** | Closed old Put; Failed Bearish entry | Safe CE strikes $\ge 22800$ decayed to ₹40 (<₹65); ₹88 strike (`22600`) blocked by ST moat | V8.2 Asymmetric Next Week Hunter implemented | `22650 CE` @ ₹96.10 / `23150 CE` @ ₹17.50 (+₹78.60 credit) |
| **Kotak OS** | Closed old Put; Failed Bearish entry | Exact same strike decay (<₹65) in current week | V8.2 Asymmetric Next Week Hunter implemented | `22650 CE` @ ₹95.55 / `23150 CE` @ ₹17.50 (+₹78.05 credit) |
| **HDFC OS** | Position #5 stuck open; Failed Bearish entry | `_get_broker_short_state` called `get_holdings()` instead of `get_positions()`; returned `UNKNOWN` | Repaired position reader; live-squared Position #5; implemented V8.2 hunter | `22650 CE` @ ₹95.05 / `23150 CE` @ ₹17.20 (+₹77.85 credit) |

---

## 🌸 7. CHHOTI BAHAN UPDATED RELEASE (14-OCT-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **Archive File** | `ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip` | Full standalone production bundle |
| **Desktop Location** | `c:\Users\pc\Desktop\ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip` | Ready for direct WhatsApp/Telegram send |
| **Local Repo Location** | `c:\Users\pc\Desktop\BHARAT-SYSTEMS\ZERODHA OS\ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip` | Permanent development mirror |
| **M1/M2 Resolution** | Continuous Kite LTP polling via `terminal_backend.py` + `block_manager.py` | Eliminates old manual block caching failure |
| **Weekly ST Addition** | V8.2 Asymmetric Dual-Expiry Hunter (`weekly_st_engine.py`) | Autonomous 2H SuperTrend 3-pulse trading engine |
| **Security Invariant** | `ALLOWED_TRADING_IP=ANY` pre-configured in local template | Zero IP lockouts on local broadband / home WiFi |
| **1-Click Launchers** | `RUN_CHHOTI_BAHAN_ZERODHA_OS.bat`, `START_CHHOTI_BAHAN_AUTO_UPDATE.bat` | Streamlit Dashboard on Port `9007` |

---

## 🚨 8. 14-OCT-2026 BROKER EXECUTION FORENSIC AUDIT & PERMANENT INVARIANTS

### 1. The Outbound IPv6 Broker Rejection Bug (Root Cause)
- **Symptom**: Orders for both M1 and Weekly ST (W1) failed to appear on the broker order book, silently failing with `[ABORT] Hedge BUY order failed or unfilled`.
- **Root Cause**: The HostAsia Linux VPS has dual-stack networking enabled. Python `requests` resolved `api.kite.trade`'s AAAA record and routed outbound traffic via IPv6 (`2a01:4f8:c014:6479::1`). Zerodha Kite API developer console only had the static IPv4 (`5.75.250.104`) whitelisted, causing Kite to reject orders with:
  > `IP (2a01:4f8:c014:6479::1) is not allowed to place orders for this app. Update allowed IPs on the Kite developer console.`
- **Permanent Invariant Enforced**:
  1. Disabled IPv6 at Linux kernel level via `/etc/sysctl.conf`:
     ```ini
     net.ipv6.conf.all.disable_ipv6 = 1
     net.ipv6.conf.default.disable_ipv6 = 1
     net.ipv6.conf.lo.disable_ipv6 = 1
     ```
  2. Forced IPv4 socket binding in [kite_executor.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/kite_executor.py):
     ```python
     import urllib3.util.connection as urllib3_conn
     urllib3_conn.HAS_IPV6 = False
     ```

### 2. M1 Staging Buffer & Anchor Refresh Invariant
- **Staging State**: Clicking `"Arm Both Wings in PENDING (Standby)"` stages strikes in SQLite in `PENDING` mode for operator review without routing market orders.
- **Stale Anchor Check Elimination**: In [block_manager.py](file:///c:/Users/Dell/Desktop/cheenna%20zerodha/block_manager.py), the `if current_ltp >= anchor_price + 2.0` guard previously blocked orders if prices moved ₹2 during staging. Now, on manual trigger or `execute_block()`, the strike anchor auto-syncs to `fresh_ltp` right before execution (`ignore_cooldown=True`).
- **Anchor Typo Correction**: Corrected Block 81 Master Anchor from `₹23,650.00` (1,000 pt typo) to **`₹22,650.00`**. Spot (`22,612`) < Anchor (`22,650`) $\implies$ `BEARISH` Regime confirmed.

### 3. Verified Broker Ground Truth (14-Oct-2026 EOD)
| System | Position Type | Leg | Strike & Contract | Lots / Qty | Fill Price | Broker Order ID | Status |
|---|---|---|---|---|---|---|---|
| **M1 Unit** | Short Call Spread | **Hedge Buy** | `NIFTY26NOV23700CE` | `5` Lots / `325` | **₹90.80** | `2110307347598450688` | **COMPLETE** |
| **M1 Unit** | Short Call Spread | **Sell Short**| `NIFTY26NOV23200CE` | `5` Lots / `325` | **₹214.81**| `2110307353327869952` | **COMPLETE** |
| **Weekly W1**| Bull Put Spread | **Hedge Buy** | `NIFTY26OCT21750PE` | `1` Lot / `65` | **₹29.90** | `2110306482795880448` | **COMPLETE** |
| **Weekly W1**| Bull Put Spread | **Sell Short**| `NIFTY26OCT22250PE` | `1` Lot / `65` | **₹92.45** | `2110306487220871168` | **COMPLETE** |

---

## 🦅 9. SUPER SUKHOI V7.0 AUTONOMOUS LADDERING UPGRADE (26-OCT-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **Super Sukhoi V7.0** (Chhoti Bahan Edition) | Autonomous Multi-Tier Scaling for M1, M2, M3 |
| **Core Architecture** | Non-invasive supervisor over `block_manager.py` | `super_sukhoi_engine.py` |
| **Trigger Matrix** | Derived from Seed M1 Anchor ($A_1$) | $M2 = A_1 \pm 2.00\%$, $M3 = A_1 \pm 4.00\%$ |
| **Compulsory Armor** | 100% 500-point OTM Hedge Helmet | **Buy Hedge FIRST ➔ Sell Leg SECOND** on Zerodha Kite |
| **Stop-Loss Policy** | Decoupled (`m_stoploss_mode = "DISABLED"`) | Eliminates whipsaw stop-outs; natural theta decay harvested |
| **Market Guard** | `is_market_session_active()` | 100% quiet hours / weekend / NSE 2026 holiday silence |
| **Dashboard Radar** | Integrated into Cockpit HUD (Port `9007`) | 1-Click Activate with 2-step confirmation modal |
| **Verification** | `test_super_sukhoi_cheenna_v7.py` | 100% Green test suite passed |




---

## 🦅 10. SUPER SUKHOI V7.1 DYNAMIC EXECUTION-ANCHORED UPGRADE (03-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **Super Sukhoi V7.1** (Chhoti Bahan Edition) | Gap-Up & Dynamic Re-Anchoring Production Release |
| **Core Architecture** | Execution-Anchored Multi-Tier Supervisor | `super_sukhoi_engine.py` |
| **Mom's Invariant** | Dynamic Re-Anchoring on Execution | $A_2 = \text{RoundTo50}(\text{Spot}_{\text{entry}})$. Eliminates theoretical gap disconnect & reversal blindness |
| **Chained Trigger Matrix** | Sequential Chaining | $M2 = A_1 \pm 2.00\%$; $M3 = \mathbf{A_2} \pm 2.00\%$. $M3$ can NEVER double-trigger on gap days |
| **Lot Inheritance** | Dynamic Mirroring from $M1$ | Inherits active $M1$ lots (e.g. 3 Lots / 195 Qty); zero fallback to 1 |
| **Directional Parity** | Single-Directional Lock | $M2$ and $M3$ strictly follow $M1$ trend regime; opposing cross-strangles blocked |
| **Block Lock Guard** | JIT Auto-Hunter Muted | `regime_engine.py` skips JIT auto-strike hunting on Super Sukhoi units |
| **Dashboard Radar** | Updated Cockpit HUD (Port `9007`) | Displays active inherited lots, dynamic $A_2$, and chained $M3$ bounds |
| **Verification** | `test_super_sukhoi_cheenna_v7_1.py` | 100% Green test suite passed |


---

## 🌸 11. CHHOTI BAHAN 3-STEP SEQUENTIAL PIPELINE UPGRADE (03-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **3-Step Sequential Operator Flow** (Chhoti Bahan Edition) | Foolproof UI workflow eliminating side-by-side button confusion |
| **Premature Lock Guard** | Gated Linear State Machine | Step 2 Lock button is hidden/disabled until Step 1 Fetch succeeds |
| **Step 1 (Input & Fetch)** | Inputs: Lots, Horizon, Premium, Anchor | Single active button: 🔍 STEP 1: FETCH & PREVIEW LIVE STRIKES |
| **Step 2 (Review & Lock)** | Inspection cards (CE/PE strikes, LTPs, SL, Net Credit) | Gated unlock: 🔒 STEP 2: CONFIRM & LOCK STRATEGY PARAMETERS |
| **Step 3 (Dual Route)** | Two mutually exclusive choices | 🚀 Option A: Execute Now (Instant Fill) vs ⏱️ Option B: Arm in Standby (3 PM Pulse) |
| **Tri-Module Parity** | pp.py, os_engine.py, weekly_st_engine.py | Universal 3-Step sequential parity across M-Units, OS, and Weekly ST |
| **Backend Invariant** | 0% change to execution calculus | lock_manager.py, super_sukhoi_engine.py, kite_executor.py 100% untouched |
| **Broker State at Deploy** | Zerodha Kite (XK7125): **100% FLAT** | 0 open positions, **+₹20,179.25 gross (+₹19,577.77 net)** secured |


---

## 🛒 12. BHARAT OPTION BUYING ENGINE (NSL v6.1 — NON-MONTHLY BREAKOUT & CHHOTI BAHAN INVARIANTS)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **Bharat Option Buying (NSL v6.1)** | Non-Monthly Weekly Reference Breakout Engine |
| **Asset & Base Sizing**| NIFTY 50 • **Strictly 1 Lot (65 Qty)** | Zero overtrading; capital risk capped at ~₹10k–₹13k |
| **Target Expiry Rule** | **Strictly Non-Monthly Expiries** | Avoids last Thursday; prevents collision with Option Selling M-Units |
| **Expiry Distance** | **~3rd to 4th Week Forward (~14–28 Days)** | If 4th week is monthly, auto-cascades to 3rd week for peak liquidity |
| **Strike Series Filter**| **Modulo 100 Only (`strike % 100 == 0`)**| Banish 50-ending strikes; eliminates illiquid fills & wide bid-ask spread |
| **Target Premium** | **₹160.00 to ₹200.00** (closest to ₹160) | Low theta decay curve with responsive directional delta ($\Delta pprox 0.38$) |
| **Gate 1 (Morning)** | **10:45 AM IST** Breakout Evaluation | Buys only if $LTP_{1045} > Ref_{930}$ (1-min historical candle close) |
| **Watchdog Loop** | **5-Minute Boundary Monitor** | At $+50\%$ profit $\implies$ **Sell Active $
ightarrow$ Sleep 30s $
ightarrow$ Rollover** |
| **Gate 2 (Afternoon)** | **03:00 PM IST** Trend Check | Hold overnight if $LTP > Ref_{930}$; Exit immediately if $LTP \le Ref_{930}$ |
| **Long-Only Shield** | `qty > 0` AND token match AND tag `NSLBUY` | All short selling positions (`qty < 0`) are 100% invisible & untouchable |
| **UI & DB Isolation** | Dedicated Standalone Page & `zerodha_buying.db` | Zero cognitive clutter ("bhashan"); zero interference with Port `9007` |

---

## 🛑 13. EMERGENCY EXIT & BROKER GROUND TRUTH RECONCILIATION UPGRADE (04-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **Broker Ground Truth Emergency Exit** | Direct Broker Square-Off & Unit Desync Resolution |
| **Root Cause Resolved** | Unit Name & Status Desync | wipe_out_and_reset_m_unit() checked only anchor_unit_name == u; missed auto-spawned blocks with notes or non-OPEN statuses |
| **M3 Button Parity** | 4-Column UI Exit Strip | Added dedicated M3 emergency close button to app.py Cockpit |
| **Broker Ground Truth Loop** | Direct Kite API Cross-Check | After closing DB records, checks kite.positions()['net'] and places market exit orders for any hanging legs |
| **Master Kill-Switch** | 1-Click Account Square-Off | Directly flattens ALL open derivative contracts on Zerodha Kite API (Shorts covered first -> Hedges sold second) |
| **Margin Safety Invariant** | Margin-Safe Execution Order | **Buy-to-Cover Shorts FIRST -> Sell Long Hedges SECOND**; 100% margin-call proof |
| **Deployment Target** | HostAsia VPS (5.75.250.104:9007) | Dual service restart: zerodha_engine.service & zerodha_dashboard.service |

---

## 🏛️ 14. M1 ASYMMETRIC DUAL-WING EXECUTION & BUFFER HYSTERESIS PROTOCOL (06-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **V6.0 / V8.0 Asymmetric Dual-Wing Engine** | Directional Trend Following with Hedged Dual-Side Capacity |
| **Dual-Wing Execution Rule**| **Simultaneous Dual-Wing Allowed** | When Spot crosses Anchor + Buffer, Put wing initiates. Existing opposing Call leg is NOT closed midday |
| **Stop-Loss Policy** | **Midday Stop-Loss 100% DISABLED** | `m_stoploss_mode = "DISABLED"`. No 25% midday whipsaw cuts; natural theta decay harvested |
| **Wrong Trade Exit Rule** | **Automatic 3:00 PM Evening Removal** | Opposing/wrong side is NOT cut midday; at 15:00 IST Continuation Pulse, engine auto-squares off opposing leg |
| **Buffer Wall Calculus** | **$\text{Anchor} \pm \text{Buffer}$ (Default: $\pm 15.0\text{ pt}$)** | Bullish Trigger = $A + B$; Bearish Trigger = $A - B$. Inside zone = NEUTRAL |
| **Sustained Stay Timer** | **5-Minute Confirmation (300 seconds)** | Spot must remain beyond trigger for 300s continuously before auto-deploy |
| **Engine Execution Guard** | **`algo_running = 'ON'` in SQLite settings** | When `algo_running = 'OFF'`, background service enters PAUSED loop; no auto-orders placed |
| **Protective Armor** | **100% 500-pt OTM Hedge Helmet** | Buy Hedge FIRST $\rightarrow$ Sell Leg SECOND; zero naked exposure at any time |
| **Mandatory Pre-Task Rule** | **Forcefully Read `GEMINI.md` & `memory.md`** | Zero guessing; cross-check ground truth before any proposal or execution |
