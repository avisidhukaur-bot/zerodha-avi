# 🧱 LEGO PROTOCOL: V8.2 SYSTEM UPGRADE & INTEGRATION BLUEPRINT
### Target: Bharat Zerodha OS — Cheenna Zerodha (Avinash Kaur / XK7125)
**Date:** 14-Oct-2026 | **Author:** Antigravity AI & Gurjeet Mamu Engineering Group

---

## 🎯 1. OBJECTIVE & ARCHITECTURAL SCOPE
To perform a complete 1:1 institutional mirror upgrade of the Brother's V8.2 codebase into Cheenna Zerodha while preserving:
1. **Gurjeet Mamu's Dedicated VPS Environment:** `5.75.250.104` (Port `9007`).
2. **Dedicated Broker Credentials:** Avinash Kaur (`XK7125`) Kite Connect API.
3. **Strict VPS Isolation:** Zero connection or references to brother's VPS (`46.224.133.16`).

---

## 🧱 2. THE 6-STEP LEGO SEQUENCE

```
[1. DIAGNOSE] ➔ [2. BLUEPRINT] ➔ [3. CODE INTEGRATION] ➔ [4. COMPILATION CHECK] ➔ [5. GIT COMMIT & PUSH] ➔ [6. VPS DUAL-SERVICE DEPLOY]
```

### Brick 1: Diagnostic & Gap Analysis
- **Problem Identified in V5.0:**
  * Invariant #5 blocked intraday Kill & Flip, keeping short put active even when Spot broke below Anchor & Buffer.
  * Stop Loss threshold was calculated on Anchor (₹189) rather than Entry Fill (₹178), causing delayed stop-out.
  * M1/M2 relied on manual/semi-static price polling rather than high-frequency live Kite LTP streams.
  * Missing W1 Weekly Option Selling (2-Hour SuperTrend Asymmetric Dual-Expiry Hunter).

### Brick 2: Core Components to Mirror & Install
| Component | Module | Responsibility |
|---|---|---|
| **Weekly ST Engine** | `weekly_st_engine.py` | 2H SuperTrend (8,3) Asymmetric Dual-Expiry Hunter (`W1` Pod) |
| **Weekly ST UI** | `ui_weekly_st.py` | Dedicated Tab 3 Cockpit with Pulse Countdown & Single Authoritative Lock |
| **M-Units Cockpit** | `ui_m_units.py` + `block_manager.py` | Continuous Kite LTP polling & JIT Auto-Hunter (~₹200 on EVEN 100s) |
| **OS-Units Cockpit** | `ui_os_units.py` + `os_engine.py` | Momentum Option Selling (OS1–OS5) on ODD 50s (`0.00%` clash) |
| **Modular UI Bricks** | `ui_header.py`, `ui_blocks.py`, `ui_logs.py` | High-density institutional dark UI components |
| **Terminal Backend** | `terminal_backend.py` + `terminal_app.py` | O(1) ultra-fast memory-cached data feeder |
| **Database Migrations** | `db.py` | `weekly_st_positions` table + schema auto-migrations |
| **Background Loop** | `main.py` | 3 daily W1 execution pulses (`11:15`, `13:15`, `15:10 IST`) + M-unit continuation |

### Brick 3: Master Rule Ground Truth (`GEMINI.md`)
- Embed all institutional behavioral protocols, math invariants, modulo filters, and tri-broker parity audits.

### Brick 4: Quality & Integrity Verification
- Python syntax compilation across all 24+ modules (`py_compile`).
- SQLite table schema auto-migration verification.

### Brick 5: Version Control
- Git add, commit, and push to remote `main`.

### Brick 6: Live VPS Production Deployment
- Update `lego1_deploy.py` to deploy all newly introduced modules.
- Upload to `/root/BHARAT-SYSTEMS/ZERODHA-OS/` on `5.75.250.104`.
- Restart `zerodha_engine.service` and `zerodha_dashboard.service` (Port `9007`).
- Verify Port 9007 HTTP 200 OK and systemd active status.
