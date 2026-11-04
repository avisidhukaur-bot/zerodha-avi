# -*- coding: utf-8 -*-
with open('GEMINI.md', 'r', encoding='utf-8') as f:
    text = f.read()

entry = """

---

## 🛒 12. BHARAT OPTION BUYING ENGINE (NSL v6.1 — NON-MONTHLY BREAKOUT & CHHOTI BAHAN INVARIANTS)

| Parameter | Specification | Notes |
|---|---|---|
| **System Version** | **Bharat Option Buying (NSL v6.1)** | Non-Monthly Weekly Reference Breakout Engine |
| **Asset & Base Sizing**| NIFTY 50 • **Strictly 1 Lot (65 Qty)** | Zero overtrading; capital risk capped at ~₹10k–₹13k |
| **Target Expiry Rule** | **Strictly Non-Monthly Expiries** | Avoids last Thursday; prevents collision with Option Selling M-Units |
| **Expiry Distance** | **~3rd to 4th Week Forward (~14–28 Days)** | If 4th week is monthly, auto-cascades to 3rd week for peak liquidity |
| **Strike Series Filter**| **Modulo 100 Only (`strike % 100 == 0`)**| Banish 50-ending strikes; eliminates illiquid fills & wide bid-ask spread |
| **Target Premium** | **₹160.00 to ₹200.00** (closest to ₹160) | Low theta decay curve with responsive directional delta ($\Delta \approx 0.38$) |
| **Gate 1 (Morning)** | **10:45 AM IST** Breakout Evaluation | Buys only if $LTP_{1045} > Ref_{930}$ (1-min historical candle close) |
| **Watchdog Loop** | **5-Minute Boundary Monitor** | At $+50\%$ profit $\implies$ **Sell Active $\rightarrow$ Sleep 30s $\rightarrow$ Rollover** |
| **Gate 2 (Afternoon)** | **03:00 PM IST** Trend Check | Hold overnight if $LTP > Ref_{930}$; Exit immediately if $LTP \le Ref_{930}$ |
| **Long-Only Shield** | `qty > 0` AND token match AND tag `NSLBUY` | All short selling positions (`qty < 0`) are 100% invisible & untouchable |
| **UI & DB Isolation** | Dedicated Standalone Page & `zerodha_buying.db` | Zero cognitive clutter ("bhashan"); zero interference with Port `9007` |
"""

if '## 🛒 12. BHARAT OPTION BUYING ENGINE' not in text:
    text = text + entry
    with open('GEMINI.md', 'w', encoding='utf-8') as f:
        f.write(text)
    print('GEMINI.md updated successfully.')
else:
    print('GEMINI.md already has Section 12.')

