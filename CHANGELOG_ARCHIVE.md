# 📦 CHANGELOG ARCHIVE — BHARAT ZERODHA OPTION SELLING ENGINE
> **Cold Storage Archive for Historical Version Post-Mortems & Audits**  
> *Target System: Zerodha Kite Option Selling App (Bharat Systems)*  
> *Active Rulebook: See GEMINI.md for current active invariants and v8.7.4+ rules.*  

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
- IPv6 Broker Rejection Bug fixed by disabling IPv6 at Linux kernel level and forcing IPv4 socket binding in `kite_executor.py`.
- M1 Staging Buffer & Anchor Refresh Invariant added to `block_manager.py`.

---

## 🦅 9. SUPER SUKHOI V7.0 AUTONOMOUS LADDERING UPGRADE (26-OCT-2026)
- Autonomous Multi-Tier Scaling for M1, M2, M3.
- Trigger matrix: $M2 = A_1 \pm 2.00\%$, $M3 = A_1 \pm 4.00\%$.
- Compulsory Armor: 100% 500-point OTM Hedge Helmet (Buy Hedge FIRST -> Sell Leg SECOND).

---

## 🦅 10. SUPER SUKHOI V7.1 DYNAMIC EXECUTION-ANCHORED UPGRADE (03-NOV-2026)
- Mom's Invariant: Dynamic Re-Anchoring on Execution: $A_2 = \text{RoundTo50}(\text{Spot}_{\text{entry}})$.
- Chained Trigger Matrix: $M2 = A_1 \pm 2.00\%$; $M3 = \mathbf{A_2} \pm 2.00\%$.
- Dynamic lot inheritance from M1.

---

## 🌸 11. CHHOTI BAHAN 3-STEP SEQUENTIAL PIPELINE UPGRADE (03-NOV-2026)
- 3-Step Sequential Operator Flow eliminating button confusion.
- Step 1 (Fetch) -> Step 2 (Lock) -> Step 3 (Execute / Arm Standby).

---

## 🛒 12. BHARAT OPTION BUYING ENGINE (NSL v6.1 — NON-MONTHLY BREAKOUT)
- Asset & Base Sizing: NIFTY 50 • Strictly 1 Lot (65 Qty).
- Non-monthly expiries, target premium ₹160–₹200.
- Standalone page on Port 9008 and `zerodha_buying.db`.

---

## 🛑 13. EMERGENCY EXIT & BROKER GROUND TRUTH RECONCILIATION UPGRADE (04-NOV-2026)
- Master Emergency Kill-Switch directly flattens all open contracts on Zerodha Kite API.
- Margin-Safe Execution Order: Buy-to-Cover Shorts FIRST -> Sell Long Hedges SECOND.

---

## 🏛️ 14. M1 ASYMMETRIC DUAL-WING EXECUTION & BUFFER HYSTERESIS PROTOCOL (06-NOV-2026)
- Simultaneous dual-wing allowed.
- Midday Stop-Loss 100% DISABLED (`m_stoploss_mode = "DISABLED"`).
- Opposing leg squared off at 15:00 IST Continuation Pulse.

---

## 🧹 15. GURJEET MAMU'S 15:02 IST ORPHAN HEDGE CLEAN-SWEEP PROTOCOL (23-NOV-2026)
- 15:00 Short Exit -> 15:02 Linked Orphan Hedge Exit.
- Pre-close peace window: 27 minutes quiet zone (15:03–15:30 IST).
