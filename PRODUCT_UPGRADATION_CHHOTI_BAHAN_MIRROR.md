# 🌸 PRODUCT UPGRADATION: CHHOTI BAHAN MIRROR INTEGRATION
### Gap Analysis & System Enhancement Report
**System:** Cheenna Zerodha OS | **Base:** V5.0 "Old & Gold" $\longrightarrow$ **Target:** V8.2 Institutional Mirror

---

## 🔍 1. GAP ANALYSIS: OLD V5.0 VS NEW V8.2

| Factor | Old V5.0 System | New V8.2 Upgraded System |
|---|---|---|
| **M1/M2 Price Stream** | Relied on semi-static instrument lookup; quotes stalled if not active in cache. | **Live Kite LTP Streaming:** Continuous 30s asynchronous thread polling (`terminal_backend.py` + `block_manager.py`). |
| **Intraday Kill & Flip** | Disabled by Invariant #5 (Decoupled Mode), causing trades to hold even if Spot broke below buffer. | **Configurable Execution Modes:** Supports both Decoupled Mode and Instant `AUTO_FLIP` on regime break. |
| **Stop Loss Formula** | Derived from Anchor Price (e.g. ₹189), causing SL trigger to be higher than actual fill price + 25%. | **Fill-Price Strict SL:** Anchored strictly to real broker execution fill price (`Fill * 1.25`). |
| **Weekly Trading** | No autonomous weekly spread strategy existed. | **Weekly ST-2H Engine (`W1`):** Complete 2-Hour SuperTrend hunter with asymmetric dual-expiry rollover. |
| **User Interface** | Monolithic single-file Streamlit layout. | **Modular 7-Tab Architecture:** Clean split into modular UI bricks (`ui_m_units.py`, `ui_weekly_st.py`, `ui_os_units.py`, `ui_header.py`). |
| **Fast Terminal Option** | Streamlit only. | **Dual Engine Interface:** Streamlit (Port `9007`) + NiceGUI Realtime Terminal (`terminal_app.py`). |

---

## 🛠️ 2. STEP-BY-STEP UPGRADE CHECKLIST

1. [x] Unpack official `ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip` bundle.
2. [x] Analyze codebase architecture, NiceGUI UI, and SuperTrend math.
3. [x] Draft Lego Blueprint & Product Specs.
4. [ ] Create institution-grade `GEMINI.md` system anchor file.
5. [ ] Copy all updated modules into root workspace:
   - `weekly_st_engine.py`
   - `ui_weekly_st.py`, `ui_m_units.py`, `ui_os_units.py`, `ui_blocks.py`, `ui_commodity.py`, `ui_equity.py`, `ui_header.py`, `ui_logs.py`
   - `terminal_backend.py`, `terminal_app.py`
   - `block_manager.py`, `app.py`, `main.py`, `db.py`, `pnl_engine.py`, `regime_engine.py`, `os_engine.py`
6. [ ] Apply Cheenna Zerodha Environment Guard:
   - Preserves VPS IP: `5.75.250.104` (Port `9007`)
   - Preserves Zerodha Account: `XK7125` (Avinash Kaur)
   - Preserves Telegram Token & Chat ID
   - Configures `ALLOWED_TRADING_IP=5.75.250.104,ANY`
7. [ ] Run Database Migration script (`chhoti_bahan_auto_update.py`).
8. [ ] Perform compilation integrity check across all modules.
9. [ ] Commit all code changes to Git and push to GitHub remote.
10. [ ] Deploy to VPS `5.75.250.104` and restart systemd services.
11. [ ] Perform end-to-end verification of Port 9007 live dashboard.
