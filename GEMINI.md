# 🏛️ GEMINI.md — BHARAT ZERODHA OPTION SELLING ENGINE
> **Master Operating Context, System Behavior Protocol & Architectural Invariants**  
> *Target System: Zerodha Kite Option Selling App (Bharat Systems)*  
> *Last Updated: 08-Oct-2026*

---

## ⚡ SYSTEM BEHAVIOR & OUTPUT PROTOCOL

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
