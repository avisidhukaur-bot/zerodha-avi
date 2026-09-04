# 🌸 ZERODHA OS V3.0 — SISTER'S LAPTOP REPAIR & UPGRADE GUIDE
### 🚀 Complete Restoration, Multi-Anchor V3 Setup & Daily Operations Manual

---

## 📱 PART 1: QUICK SHAREABLE MESSAGE (WhatsApp / Telegram Copy-Paste)

> **Copy-paste this message directly on WhatsApp / Telegram:**

```text
🌸 ZERODHA OS V3.0 UPGRADE & REPAIR GUIDE (Apne Laptop ke liye) 🌸

Hello! System ko bilkul latest V3.0 par upgrade aur repair karne ke liye ye 3 simple steps follow karo:

STEP 1: Folder me jao
- Apne Zerodha OS ke folder me jao.

STEP 2: 1-Click Auto Repair Run karo
- Agar Git install hai to CMD me likho:
  git fetch origin master && git reset --hard origin/master && git pull origin master
  python sister_v3_auto_repair.py
- Ya fir folder me "START_V3_REPAIR.bat" file par DOUBLE CLICK karo!
(Ye script tumhari purani corrupt changes clean kar degi, secrets.txt aur database ko safe rakhegi aur sabhi V3 features install kar degi).

STEP 3: Start Trading Dashboard
- Folder me "RUN_ZERODHA_V3.bat" par DOUBLE CLICK karo.
- Browser me automatically http://localhost:9007 open ho jayega.
- Har subah 9:00 AM par Sidebar me jakar "📲 Send OTP" ya "TOTP" se Zerodha connect karo.

Bas! Tumhara system fully clean aur upgraded ho gaya! 🚀
```

---

## 🛠️ PART 2: DETAILED STEP-BY-STEP REPAIR & UPGRADE INSTRUCTIONS

Aapke laptop me jo purana V2 code tha jisme modifications se crash ho raha tha, use hatakar official **V3.0 Autonomous Pod Engine** par lane ke 2 asaan tarike hain:

---

### 🔹 OPTION A: 1-Click Auto Repair (Recommended — 30 Seconds)

1. **Complete V3 Package Unzip Karein**:
   - `ZERODHA_OS_V3_SISTER_COMPLETE_PACKAGE.zip` file ko apne laptop ke folder me extract/unzip karein.
2. **Double-Click `START_V3_REPAIR.bat`**:
   - Is batch file par double-click karein.
   - Script automatically:
     - Aapki purani `secrets.txt` credentials aur database ka **safe timestamped backup** bana degi.
     - Database me V3.0 ke sabhi naye columns (`anchor_unit_name`, `master_anchor_price`, `regime_buffer`, `side_type`) bina data khoe add kar degi.
     - `requirements.txt` ki sabhi libraries verify/install kar degi.
     - Sabhi files ka syntax compile check karegi.
     - Desktop/Folder me 1-click launchers bana degi.
3. **Double-Click `RUN_ZERODHA_V3.bat`**:
   - Yeh background trading engine aur visual web dashboard ko ek sath launch kar dega.
   - Default browser me `http://localhost:9007` automatically open ho jayega!

---

### 🔹 OPTION B: 1-Line Git Reset & Upgrade (Agar Git Installed Hai)

Agar aapke folder me Git setup hai to Command Prompt (CMD) me ye 2 commands chalayein:

```bash
cd C:\path\to\ZERODHA-OS
git fetch origin master
git reset --hard origin/master
git pull origin master
python sister_v3_auto_repair.py
```

Isse sari gadbad aur broken files instant hat jayengi aur GitHub se 100% verified V3.0 code restore ho jayega.

---

## 🔑 PART 3: `secrets.txt` CONFIGURATION

Apne folder me **`secrets.txt`** file ko Notepad me open karein aur verify karein ki aapke credentials sahi hain:

```text
# 🔑 Zerodha API Credentials
KITE_API_KEY=tumhari_api_key_yahan
KITE_API_SECRET=tumhari_api_secret_yahan
KITE_CLIENT_CODE=tumhara_user_id (e.g. XM2086)
KITE_PASSWORD=tumhara_zerodha_password
KITE_TOTP_KEY=tumhara_google_authenticator_secret (optional)

# 📱 Mobile Alerts (ntfy app topic)
NTFY_TOPIC=tumhara_ntfy_topic

# 📨 Telegram Alerts
TELEGRAM_TOKEN=tumhara_telegram_bot_token
TELEGRAM_CHAT_ID=tumhari_telegram_chat_id

# Trading Configuration
ALLOWED_TRADING_IP=ANY
```

---

## 🎯 PART 4: V3.0 KE NAYE & POWERFUL FEATURES

| Feature | Kya Fayda Hai? |
| :--- | :--- |
| **🎯 Multi-Anchor Pods (M1, M2, M3)** | Ek hi expiry date (jaise 24-Jul) me alag-alag spot prices par naye blocks bana sakte hain bina purane blocks ko disturb kiye. |
| **🛡️ Strict Regime Execution Guard** | Agar market Bullish hai to system Call (CE) ko execute nahi karega (brokerage bachegi). Spot cross hote hi automatic execute hoga. |
| **⚙️ Inline Strike & Anchor Editor** | Har block ke niche hi anchor price aur lots change karne ka option hai. Screen par idhar-udhar dhundhne ki zarurat nahi. |
| **💰 Orphan Hedge Profit Lock** | Jab Sell leg target par band ho jata hai, bacha hua Hedge leg automatically alert deta hai taaki profit lock kiya ja sake. |
| **🔴 200 DMA Red Alert Banner** | Agar aapke portfolio ka koi stock 200 DMA ke niche jata hai to top par instant warning alert dikhta hai. |
| **🛢️ MCX Commodities FUT** | Gold, Silver, Crude Oil, Natural Gas ka dedicated separate trading tab. |

---

## ⏰ PART 5: DAILY MORNING ROUTINE (Trading Protocol)

1. **Subah 9:00 AM IST**:
   - Laptop on karke `RUN_ZERODHA_V3.bat` par double click karein.
   - Dashboard par left sidebar me jakar:
     - `📲 Send OTP to Mobile` click karein aur OTP dalkar connect karein, YA
     - 6-digit `TOTP Code` dalkar `🔌 Connect with TOTP` click karein.
   - Status `🟢 Zerodha API: CONNECTED` dikhna chahiye.
2. **Subah 9:15 AM (Market Open)**:
   - Agar market me naya anchor level set karna hai:
     - Unit Pod controller me `⚡ Lock Spot` click karein aur `💾 Save Unit Anchor` karein.
   - Agar naya block banana hai:
     - Top par **New Block Form** me Unit name (e.g. `M1` ya `M2`), Expiry date aur Side select karke `📦 Create Block` karein.
3. **Sham 3:30 PM (Market Close)**:
   - Dashboard me **Summary** button dabakar pure din ka P&L Telegram par bhejein.
   - Agar system band karna hai to `STOP_ZERODHA_V3.bat` par double click karein.

---

### 📞 Troubleshooting & Emergency

- **Brokerage Order rejected?**: Zerodha me funds aur margin check karein.
- **Port 9007 already in use?**: `STOP_ZERODHA_V3.bat` chalayein aur fir `RUN_ZERODHA_V3.bat` dobara start karein.
- **Data mismatch?**: Sidebar me **`🔧 Reconcile / Sync DB`** button dabayein.
