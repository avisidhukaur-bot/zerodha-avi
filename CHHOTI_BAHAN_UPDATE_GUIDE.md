# 🌸 ZERODHA OS V8.2 — CHHOTI BAHAN COMPLETE SYSTEM UPDATE & OPERATING GUIDE
### 🚀 Directional M-Units Auto-Price Fetch + W1 Weekly Option Selling + OS Hunter Architecture

---

## 📱 PART 1: WHATSAPP / TELEGRAM SHAREABLE MESSAGE (DIRECT COPY-PASTE)

> **Bahan ko bhejne ke liye ye message directly copy karke send karein:**

```text
🌸 ZERODHA OS V8.2 UPDATED VERSION (Special Chhoti Bahan Edition) 🌸

Hello! System ko bilkul latest V8.2 version par update kar diya gaya hai. Isme M1 aur M2 me price automatically fetch na hone wali problem permanently fix ho gayi hai, aur Weekly Option Selling (W1 Engine) ka naya feature bhi add ho gaya hai!

🚀 UPDATE KARNE KE 3 AASAAN STEPS:

STEP 1: Zip File Extract Karo
- "ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip" ko apne computer/laptop me kisi folder me Unzip (Extract) kar lo.

STEP 2: 1-Click Auto Update Run Karo
- Folder ke andar "START_CHHOTI_BAHAN_AUTO_UPDATE.bat" par DOUBLE CLICK karo.
- Ye tumhari purani secrets.txt aur database ka automatic backup bana dega aur sabhi naye tables (Weekly ST, M-Units) safely update kar dega.
- Agar pehli baar use kar rahi ho to "secrets.txt" me apni Zerodha API key, secret aur password daal dena (ALLOWED_TRADING_IP=ANY pehle se set hai).

STEP 3: Dashboard Start Karo
- Folder me "RUN_CHHOTI_BAHAN_ZERODHA_OS.bat" par DOUBLE CLICK karo.
- Browser me automatically http://localhost:9007 open ho jayega!
- Subah 9:00 AM par Sidebar me Zerodha login kar lena.

✅ Fayda: M1 aur M2 me automatically live market prices aayenge, aur Weekly trades bhi aaram se dekh sakogi! 🌟
```

---

## 🔍 PART 2: WHY M1 & M2 PRICES FAILED IN OLD VERSION VS NEW FIX

| Factor | Purana Old Version (Jo Bahan ke paas tha) | Naya V8.2 Version (Updated Chhoti Bahan Edition) |
|---|---|---|
| **M1 & M2 Price Polling** | ❌ Manual ya static instrument ID mapping; LTP stream stuck ho jati thi agar strike manually active na ho. | ✅ **Automatic Live Kite LTP Feeder** (`terminal_backend.py` + `block_manager.py` + `pnl_engine.py` continuous 30s cycle). |
| **JIT Dynamic Strike Hunter** | ❌ Strikelist dynamic nahi thi; spot move hone par prices gayab ho jaate the. | ✅ **JIT Dynamic Auto-Hunter (~₹200 on EVEN 100s)**; spot change hote hi live premium aur strike cards dynamically refresh hote hain. |
| **Weekly Option Selling (W1)** | ❌ Missing / Purane version me weekly trades available nahi the. | ✅ **V8.2 2-Hour SuperTrend Asymmetric Dual-Expiry Hunter** (Bull Put / Bear Call Spread with 500pt protective armor). |
| **Rules & Memory Invariants** | ❌ Incomplete or missing rule set. | ✅ **`GEMINI.md` & `memory.md` full system truth files** permanently bundled inside. |
| **IP Whitelist Guard** | ❌ Remote VPS IP hardcoded hone par home laptop par engine block ho jaata tha. | ✅ **`ALLOWED_TRADING_IP=ANY`** pre-configured for local laptop use. |

---

## 🛠️ PART 3: DETAILED INSTALLATION & UPDATE PROCEDURE

### Step 1: ZIP File Unpack
1. File ko download karein: `ZERODHA_OS_UPDATED_VERSION_CHHOTI_BAHAN.zip`.
2. Right-click karke **Extract All** karein (e.g. `C:\ZERODHA_OS` ya Desktop par).

### Step 2: 1-Click Auto Update & Database Migration
1. Folder open karein aur **`START_CHHOTI_BAHAN_AUTO_UPDATE.bat`** par double click karein.
2. Script automatically:
   - Purane `secrets.txt` aur `zerodha_trader.db` ka timestamped backup banayegi (`backup_chhoti_bahan_YYYYMMDD_HHMMSS/`).
   - Pip requirements check/install karegi (`pip install -r requirements.txt`).
   - SQLite database me missing columns aur isolated `weekly_st_positions` table initialize karegi.
   - Code files ka syntax compile check karegi.

### Step 3: `secrets.txt` Configuration
`secrets.txt` ko Notepad me open karein aur verify karein:
```text
KITE_API_KEY=tumhari_api_key
KITE_API_SECRET=tumhari_api_secret
KITE_CLIENT_CODE=tumhara_user_id
KITE_PASSWORD=tumhara_zerodha_password
KITE_TOTP_KEY=tumhara_totp_secret_key
ALLOWED_TRADING_IP=ANY
```
*(Agar pehle se credentials the, to auto-update script unhe waise ka waisa safe rakhti hai).*

### Step 4: System Run Karein
1. **`RUN_CHHOTI_BAHAN_ZERODHA_OS.bat`** par double click karein.
2. Background Trading Engine start ho jayega aur Chrome/Edge browser me dashboard open ho jayega:
   👉 **`http://localhost:9007`**
3. System ko stop karne ke liye **`STOP_CHHOTI_BAHAN_ZERODHA_OS.bat`** par double click karein.

---

## 🎁 BONUS FEATURE: W1 WEEKLY OPTION SELLING ENGINE (V8.2)

Is package me **Weekly Option Selling (W1 Engine)** automatically activate ho gaya hai:
- **Regime**: 2-Hour NIFTY Spot Candles par SuperTrend (8, 3) calculate hota hai.
- **Bullish Market**: Bull Put Spread deploy hota hai (Sell OTM PE @ ₹80-₹100 + Buy PE Hedge @ -500 pts).
- **Bearish Market**: Bear Call Spread deploy hota hai (Sell OTM CE @ ₹80-₹100 + Buy CE Hedge @ +500 pts).
- **Asymmetric Next-Week Hunter**: Agar current week ke strikes decay ho chuke hain (<₹65), engine automatically Next-Week expiry ke safe ₹80 strikes scan karke trade karta hai!

---

## ⏰ DAILY OPERATING ROUTINE

1. **Subah 09:00 AM IST**:
   - Laptop on karke `RUN_CHHOTI_BAHAN_ZERODHA_OS.bat` start karein.
   - Left Sidebar me Zerodha connect status `🟢 Zerodha Kite: CONNECTED` check karein.
2. **09:15 AM - 03:30 PM (Market Hours)**:
   - System autonomously M1-M4 aur W1 Weekly positions ko monitor karta hai.
   - Har 30 seconds me live prices and P&L screen par automatically update hote hain.
3. **03:30 PM (Market Close)**:
   - `STOP_CHHOTI_BAHAN_ZERODHA_OS.bat` chalakar engine ko cleanly band kar sakte hain.
