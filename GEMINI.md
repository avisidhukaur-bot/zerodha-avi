# 🏛️ GEMINI.md — BHARAT ZERODHA OPTION SELLING ENGINE
> **Master Operating Context, System Behavior Protocol & Architectural Invariants**  
> *Target System: Zerodha Kite Option Selling App (Bharat Systems)*  
> *Version: v8.7.7-SMART-LIMIT-CHASER | Last Updated: 27-Nov-2026*  
> *Historical Archive: See CHANGELOG_ARCHIVE.md for versions prior to v8.3.*  

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
- **Zero Fluff**: Never include introductory filler, polite sign-offs, or generic disclaimers.
- **Direct to Point**: Always start the response directly with the deliverable, heading, or data table.

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

## 🗺️ 2. PERMANENT VPS PORT & SERVICE MAP

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

---

## 🎯 3. TRADING ARCHITECTURE RULES (M-UNITS vs OS SYSTEM vs W1)

| Feature | M-Unit Systems (`M1`, `M2`, `M3`) | OS System (`OS1`–`OS5`) — V8.1 | Weekly ST Engine (`W1`) — V8.2 |
|---|---|---|---|
| **Strike Series** | **`00`-Ending Series** (`22600, 22700, 22800...`) | **`50`-Ending Series** (`22550, 22650, 22750...`) | Dynamic 50-strike grid based on Regime |
| **Modulo Filter** | `strike % 100 == 0` | `strike % 100 == 50` | `min_prem <= LTP <= max_prem` (~₹80 target) |
| **Protective Armor** | Integrated Hedge Buy | Helmet Hedge (`sell_strike ± hedge_dist`) | Synthetic Protective Armor (`±500 pts`) |
| **Mathematical Overlap** | **`0.00%`** Collision with OS | **`0.00%`** Collision with M-Units | Disjoint execution table (`weekly_st_positions`) |
| **Execution Cadence** | Continuous (30s P&L monitor) | Continuous (30s monitor) | **3 Pulses/Day**: `11:15`, `13:15`, `15:10 IST` (+ Mon) |

---

## 🛡️ 4. HARD INVARIANTS & WHITE GLASS BROKER GROUND TRUTH

1. **Broker is Single Source of Truth**: SQLite DB (`zerodha_trader.db`) is a mirror. Execution decisions must always verify broker ground truth via `kite.positions()['net']`.
2. **Three-State Broker Position Reconciliation (`SHORT` / `FLAT` / `UNKNOWN`)**:
   - `SHORT`: Broker holds confirmed net short.
   - `FLAT`: Broker confirmed 0 position.
   - `UNKNOWN`: Broker connection lost, API timeout, or unparseable state $\implies$ **FAIL-SAFE: Engine does NOTHING**.
3. **Margin Protection Invariant**:
   - Entry: **Buy Hedge FIRST** $\rightarrow$ **Sell Short SECOND**.
   - Exit: **Buy-to-Cover Short FIRST** $\rightarrow$ **Sell Hedge SECOND**.

---

## 🚀 5. GURJAS'S LEGO PROTOCOL & DUAL-SERVICE DEPLOYMENT PLAYBOOK

```
[1. DIAGNOSE] ➔ [2. BLUEPRINT] ➔ [3. APPROVAL] ➔ [4. SINGLE-BRICK CODE] ➔ [5. DUAL-SERVICE DEPLOY] ➔ [6. VERIFY]
```
- Dual-Service Invariant: When deploying, ALWAYS clean bytecode cache (`__pycache__`) and restart BOTH `zerodha_engine.service` and `zerodha_dashboard.service` (Port `9007`).

---

## 🏛️ 16. GURJEET MAMU'S 3-PULSE M-UNIT CADENCE (11:00, 13:00, 14:57 IST) WITH ±15-PT BUFFER (24-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **V8.3 3-Pulse Hysteresis Cadence** (Gurjeet Mamu's Standard) | Triple daily decision checkpoints for M-Units (`M1`, `M2`, `M3`) |
| **Triple Pulse Windows** | **`11:00` (Morning), `13:00` (Midday), `14:57` (Evening)** | 3-minute evaluation triggers (`11:00–11:03`, `13:00–13:03`, `14:57–15:02`) |
| **Buffer Zone Calculus** | **$\text{Anchor} \pm 15.0\text{ pt}$ Hysteresis Wall** | Bullish: $Spot \ge Anchor + 15.0$; Bearish: $Spot \le Anchor - 15.0$ |
| **Chop / Sideways Shield**| **Inside $\pm 15.0\text{ pt}$ = `NEUTRAL` (ZERO CUTS)** | Both wings preserved untouched to harvest natural theta decay |
| **Trending Day Action** | **Decisive Breakout ➔ Cut Opposing Short & Hedge** | Bullish continues PUT (cuts CALL); Bearish continues CALL (cuts PUT) |
| **Evening Carry Guard** | **14:57 Broker Hedge Ground Truth Verification** | Winning leg continued overnight ONLY if active long hedge verified on Kite |

---

## 🦅 17. SUPER SUKHOI V8.7.6 M1-ATTACHMENT & BROKER LOT CEILING (27-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **v8.7.6-SUKHOI-M1-CLOSE-AUTO-DISARM** | Hard-Coded M1-Attachment & Anti-Duplicate Firewall |
| **Lifecycle Anchor** | **Strictly Attached to M1** | Super Sukhoi lives and dies with M1. It cannot run or trigger without active M1. |
| **Auto-Disarm Hook** | **`_auto_disarm_sukhoi_if_m1()`** | Hooked in `close_strike()`, `kill_block()`, `delete_block()`, `wipe_out_and_reset_m_unit()`. On M1 close (0 open strikes) $\implies$ auto-disarms (`super_sukhoi_active = '0'`), purges all anchor keys, and alerts Telegram. |
| **Pre-Condition Guard**| **M1 Active Pre-Condition** | `evaluate_super_sukhoi_cycle()` queries live broker positions. If M1 has 0 open strikes $\implies$ immediate auto-disarm + abort. Zero stale DB cache fallback. |
| **Broker Lot Ceiling** | **`execute_strike()` Hard Ceiling** | Checks broker net short before routing order. If existing short $\ge$ unit locked limit (e.g. 195 qty / 3 lots), **HARD ABORTS with `[REJECT-DUPLICATE-BLOCK]`**. |
| **Clean-Slate Sentinel**| **09:00 AM Morning Purge** | Replaces old strike reset. Automatically purges previous day's stale `PENDING` strikes so zombie orders can never execute at 09:15 AM open. |

---

## 🎯 18. SMART MARKETABLE LIMIT CHASER & BROKER GROUND TRUTH GATE (27-NOV-2026)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **v8.7.7-SMART-LIMIT-CHASER** | SEBI/Exchange Compliant Limit Order Execution & Autonomous Chaser |
| **Zero Market Orders** | **Plain MARKET Orders 100% Banned** | All entries, exits, square-offs, and emergency kills route through `execute_marketable_limit_with_chaser()`. |
| **Marketable Limit Pricing**| **LTP $\pm 10\%$ Dynamic Buffer** | BUY: $\text{round}(\text{LTP} \times 1.10, 1)$; SELL: $\max(0.50, \text{round}(\text{LTP} \times 0.90, 1))$. Instant fill rate > 99%. |
| **Autonomous Chaser Sentinel**| **10s Watchdog + 3-Step Modification** | Polls order book every 2s for 10s. If market jumps away and order is unfilled, queries fresh LTP and modifies order dynamically (up to 60s max). |
| **Zero-Disconnect Gate**| **Mandatory Position Reconciliation** | `wipe_out_and_reset_m_unit()` verifies `kite.positions()`. If ANY leg remains non-zero on Kite, **DB block is NEVER deleted** (abort delete + alert). |
