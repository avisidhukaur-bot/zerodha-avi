# 🔷 ZERODHA OPTION SELLING ENGINE — SISTER'S GUIDE
### 🌸 Welcome Guide for Operators (Hinglish + Hindi)

Yeh guide aapko step-by-step batayegi ki Zerodha Option Selling Engine ko apne laptop ya VPS (Cloud Server) par kaise chalana hai aur dashboard ko kaise control karna hai.

---

## 🖥️ 1. DASHBOARD KAISAY DIKHTA HAI? (Visual Walkthrough)

*Aapko system ka dashboard bilkul Zerodha ke orange-gradient styling jaisa premium aur modern dikhega. Dashboard ke main sections ye hain:*

### ⚡ A. Header Bar (Top Section)
* **Title**: `📈 Zerodha OptionSelling Engine`
* **Status Pills**: Aapko wahan do badges dikhenge:
  * `LIVE` (Green colour): Iska matlab system live broker se connected hai.
  * `ALGO ON` (Green) ya `ALGO OFF` (Red): Yeh batata hai ki trading script background mein chal rahi hai ya nahi.
* **Portfolio P&L**: Sabse bada text jo right side mein dikhega.
  * Agar profit hai to **Green colour** mein `+Rs X,XXX.XX` dikhega.
  * Agar loss hai to **Red colour** mein `-Rs X,XXX.XX` dikhega.
* **Active stats**: Wahan active blocks aur open positions ka total count bhi dikhega.

### 📁 B. Sidebar (Left Control Panel)
* **Mode Toggles**:
  * **Algo Running (ON/OFF)**: Is button ko off karke aap trading pause kar sakti hain.
  * **Master Alerts Enabled**: Telegram aur Mobile alerts ko chalu ya band karne ke liye.
* **Zerodha API Login status**: 
  * Agar green tick ke sath `🟢 Zerodha API: CONNECTED` likha hai to sab sahi hai.
  * Agar `🔴 Zerodha API: NOT CONNECTED` likha hai, to aapko login karna hoga.
* **🔌 MANUAL OTP LOGIN**:
  * Har subah **9:00 AM IST** ke aaspas aapko is dashboard par aana hai.
  * **Option A**: `📲 Send OTP to Mobile` par click karein. Aapke phone par SMS/Email OTP aayega, use enter karke `🔌 Verify & Connect` click karein.
  * **Option B**: Agar aapne Google Authenticator set kiya hai, to 6-digit TOTP code dalkar `🔌 Connect with TOTP` click karein.
* **🔧 Reconcile / Sync DB**: Agar kabhi lagta hai ki broker aur app ka data alag hai, to is button ko click karke data sync kar sakti hain.
* **💾 Save Credentials**: Aap yahan se bhi apni Zerodha API key aur passwords update karke save kar sakti hain.

### 📊 C. Main Screen (Right Panel)
* **Active Expiry Cards**: Har active trade block ka ek box hoga. Usme active strikes, unka entry price, exit target, live price aur unka separate P&L table form mein dikhega.
* **New Block Form**: Naya trade set karne ke liye, yahan se expiry date (jaise: `02-Jul-2026`) aur type select karke block banate hain.
* **New Strike Form**: Expiry block ke andar strikes (jaise PE sell, CE sell aur unke hedges) ko add karne ke liye.
* **Trade History Table**: Din bhar ke saare trades aur orders ki detailed list page ke sabse neeche table mein dikhayi degi.

---

## 🛠️ 2. PREREQUISITES (Kya kya setup chahiye?)

App ko run karne ke liye aapko ye cheezein chahiye:
1. **Zerodha Developer API Access**:
   * `https://developer.kite.trade/` par jaakar signup karein.
   * "Kite Connect" subscription buy karein (Zerodha takes ₹2000/month).
   * "Create New App" par click karein. Redirect URL mein `http://127.0.0.1:9007/` daalein.
   * Wahan se aapko **API Key** aur **API Secret** milega.
2. **Telegram Bot Setup**:
   * Telegram par `@BotFather` search karein aur `/newbot` likhein. Bot ka naam set karke **Token** copy karein.
   * Telegram par `@userinfobot` search karein aur message bhejein, wahan se apni **Chat ID** copy karein.
3. **ntfy.sh Mobile Alerts (Free)**:
   * Apne phone (Android/iPhone) par `ntfy` app download karein.
   * Koi bhi ek unique naam sochein (e.g., `sister_zerodha_alerts_2026`) aur app mein add karein.

---

## 🔑 3. secrets.txt SETUP KAREIN

Apne unzipped folder mein jaakar **`secrets.txt`** file ko Notepad mein kholo aur apni details bharo (bina kisi space ke):

```text
# 🔑 Zerodha API Credentials
KITE_API_KEY=tumhari_api_key_yahan_daalo
KITE_API_SECRET=tumhari_api_secret_yahan_daalo
KITE_CLIENT_CODE=tumhara_zerodha_user_id (e.g. XM2086)
KITE_PASSWORD=tumhara_zerodha_password
KITE_TOTP_KEY=tumhari_google_authenticator_key (optional)

# 📱 Mobile Alerts (ntfy app topic name)
NTFY_TOPIC=tumhara_ntfy_topic_yahan_daalo

# 📨 Telegram Alerts Configuration
TELEGRAM_TOKEN=tumhara_telegram_bot_token_yahan_daalo
TELEGRAM_CHAT_ID=tumhari_telegram_chat_id_yahan_daalo

# 🖥️ VPS Details (Agar VPS par deploy karna hai)
ALLOWED_TRADING_IP=ANY
VPS_IP=tumhare_vps_ka_ip
VPS_USER=root
VPS_PASSWORD=tumhare_vps_ka_password
```

---

## 🚀 4. APP KAISAY CHALAYEIN?

Aap is app ko do tarike se chala sakti hain:

### 💻 OPTION A: Apne Laptop Par Chalana
Agar aap cloud VPS nahi lena chahte aur apne laptop par hi run karna chahte hain:
1. **Python Install Karein**: Apne laptop par Python (version 3.10 ya upar) download aur install karein.
2. **Command Prompt (CMD) Kholein**: App ke folder mein jaakar CMD kholein aur likhein:
   ```bash
   pip install -r requirements.txt
   ```
3. **Background Trading Engine Start Karein**:
   ```bash
   python main.py
   ```
   *(Isko open hi rehne dein, ye background mein trading sambhalta hai).*
4. **Dashboard Open Karein**: Naya CMD tab kholein aur likhein:
   ```bash
   streamlit run app.py --server.port 9007
   ```
5. **Browser check**: Browser mein automatic dashboard khul jayega `http://localhost:9007` par.

---

### ☁️ OPTION B: Cloud VPS Par Deploy Karna (Recommended)
Agar aap chahte hain ki app continuous cloud par chalta rahe aur laptop band hone par bhi band na ho (HostAsia / Hostinger VPS):
1. **Laptop par setup**: Apne laptop par Python install karein aur CMD mein `pip install -r requirements.txt` chalayein.
2. **secrets.txt Fill Karein**: Apne `secrets.txt` mein VPS_IP, VPS_USER (root), aur VPS_PASSWORD sahi se fill karein.
3. **One-Click Deploy Command**: CMD mein bas ye likh kar Enter maarein:
   ```bash
   python lego1_deploy.py
   ```
4. **Auto-Deployment**: Script automatic aapke VPS par codebase copy kar degi, saare packages install karegi aur services (`zerodha_engine` & `zerodha_dashboard`) ko cloud background systemd services mein chalu kar degi.
5. **Dashboard Access**: Deploy complete hone par screen par link dikhega. Aap direct open kar sakti hain:
   ```text
   http://YOUR_VPS_IP:9007
   ```

---

## ☀️ 5. ROJANA SUBAH KYA KARNA HAI? (Daily Operations)

1. Subah **9:00 AM IST** se pehle Dashboard open karein.
2. Sidebar mein **`🔌 MANUAL OTP LOGIN`** par jaakar OTP generate karein ya direct Google Authenticator ka code daalein.
3. Connect hone ke baad verify karein ki top status bar par **`LIVE`** aur **`ALGO ON`** ke green badges aa gaye hain.
4. Bas! System ab trading ke liye taiyaar hai. Aap dashboard band kar sakti hain, engine background mein trade chalata rahega!
