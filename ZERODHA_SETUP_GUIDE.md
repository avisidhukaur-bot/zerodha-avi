# 🔷 ZERODHA OPTION SELLING APP — COMPLETE SETUP GUIDE
### For: Non-Coder Operator | Hindi + English (Hinglish)

Yeh guide tumhein step-by-step batayegi ki Zerodha Kite Connect API key kaise banani hai, Google 2FA (TOTP) key kaise nikalni hai, aur mobile notifications ke liye `ntfy.sh` topic kaise setup karna hai.

---

## 📦 STEP 1: secrets.txt Kaise Fill Hoga?

App ke folder mein **`secrets.txt`** file pehle se maujood hai. 
1. Notepad mein **`secrets.txt`** file ko direct kholo.
2. Niche diye gaye tarike se details laakar isme apni values fill/update karo aur save kar do.

---

## 🔑 STEP 2: Zerodha Kite Connect API Keys Kaise Banayein?

Zerodha ke live trading parameters ko chalane ke liye ek developer API subscripton chahiye hoti hai:

1. **Register Karo**:
   - `https://developer.kite.trade/` website pe jaao.
   - **Sign Up** pe click karke account banao (yeh tumhare normal Zerodha account se alag website hai, yahan naya user account banega).
2. **Subscription Buy Karo**:
   - Log in karne ke baad, dashboard pe **"Kite Connect"** api access buy karne ka option milega.
   - Zerodha takes **₹2,000 per month** for the trading API. Account mein cards/netbanking se balance load karke ise subscribe karo.
3. **App Create Karo**:
   - Click on **"Create New App"**.
   - **App Name**: `OptionSellingApp` (kuchh bhi rakh sakte ho).
   - **Kite User ID**: Apna normal Zerodha login user ID dalo (e.g. `140003749`).
   - **Redirect URL**: Isme **`http://127.0.0.1:9007/`** dalo (ya phir system dashboard URL `http://46.224.133.16:9007/` dalo).
   - **Description**: `Automated Options Selling Engine`.
   - Submit pe click karo.
4. **Keys Copy Karo**:
   - App page pe tumhein do chijein dikhengi:
     - **API Key**: (e.g. `72c3fa56c5...`) -> notepad mein `KITE_API_KEY=` ke aage dalo.
     - **API Secret**: (e.g. `97f431b7a2...`) -> notepad mein `KITE_API_SECRET=` ke aage dalo.

---

## 🔐 STEP 3: Zerodha TOTP (Google Authenticator) Key Kaise Nikalein?

Daily morning login automation ke liye, system ko Google Authenticator jaisi ek 32-character ki "TOTP Key" chahiye hoti hai:

1. Log into your Zerodha profile: `https://kite.zerodha.com/` on laptop.
2. Profile screen ke top-right icon pe click karke **"My Profile"** or **"Console"** settings mein jaao.
3. **"Password & Security"** section pe click karo.
4. **"2FA TOTP"** setup tab pe jaao. (Agar pehle se app set hai to "Regenerate TOTP" pe click karo).
5. Screen par ek **QR Code** dikhega.
6. **⚠️ IMPORTANT:** QR Code ke niche blue colour mein ek link hoga **"Can't scan? Copy key"** ya **"Copy Key"**.
7. Us key ko click karke copy kar lo! Yeh 32-characters ka ek code hota hai (e.g. `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP`).
8. Paste this key into notepad: `KITE_TOTP_KEY=YOUR_KEY_HERE`. 
   - **Note:** Agar aap daily mobile OTP dalkar manual login karna chahte hain, toh is step ko skip kar sakte hain aur secrets.txt mein `KITE_TOTP_KEY=YOUR_TOTP_SECRET_KEY` hi chhod sakte hain (yeh optional hai).


---

## 📱 STEP 4: ntfy.sh Mobile Alerts Setup Karo (Push Alerts)

ntfy.sh ek free service hai jisse mobile screen par direct notifications aate hain bina Telegram khole:

1. **Subscribing to alerts is FREE and requires NO account creation!**
2. Ek unique topic name socho (kuchh bhi random name, e.g. `gurjeet_options_selling_alerts_2026`).
3. Dalo ise notepad mein: `NTFY_TOPIC=gurjeet_options_selling_alerts_2026`.
4. **Apne Phone mein app install karo**:
   - Play Store (Android) ya App Store (iPhone) se **`ntfy`** naam ki app search karke download karo.
   - App kholo aur **`+` (Subscribe)** button pe click karo.
   - Apne socha hua topic name dalo (e.g. `gurjeet_options_selling_alerts_2026`) aur subscribe par click karo.
5. Bas! Jab bhi system order dalega, tumhare mobile screen par direct push alert pop up hoga.

---

## 📨 STEP 5: Telegram Chat ID Kaise Nikalein?

Telegram notifications setup karne ke liye:

1. **Telegram Chat ID**:
   - Telegram pe search karo bot **`@userinfobot`**.
   - Use message bhejo `/start`.
   - Woh reply mein ek number dega `Id: 586422450`.
   - Use `TELEGRAM_CHAT_ID=` ke aage dalo.
2. **Telegram Bot Token**:
   - Apne bot se signals paane ke liye, Telegram **`@BotFather`** search karo.
   - Command do `/newbot`, bot name dalo (e.g. `MyOptionAlertsBot`).
   - BotFather ek token dega (`8600742889:AAGUn...`).
   - Use `TELEGRAM_TOKEN=` ke aage dalo.

---

## 📝 secrets.txt Summary (Final Look)

Tumhare `secrets.txt` ke andar ye sab parameters filled hone chahiye:
```text
KITE_API_KEY=72c3fa56c5ce4592bae26e8bcf7a06de
KITE_API_SECRET=97f431b7a20447bb814550dc880b7f8b
KITE_CLIENT_CODE=140003749
KITE_PASSWORD=Gurjeet_Kite_Password
KITE_TOTP_KEY=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP

NTFY_TOPIC=gurjeet_options_selling_alerts_2026

TELEGRAM_TOKEN=8600742889:AAGUn2v7aAkYGUKXKxoPaeLSQNPFGBUEhGE
TELEGRAM_CHAT_ID=586422450

ALLOWED_TRADING_IP=ANY
VPS_IP=46.224.133.16
VPS_USER=root
VPS_PASSWORD=U4CJs4HKbMMJ
```

---

## ☀️ STEP 6: Daily Operations Checklist (How to use)

### Option A: Manual 6-Digit OTP Login (Recommended for security)
1. Har subah **9:00 AM IST** se pehle dashboard URL open karo: **`http://46.224.133.16:9007`**
2. Sidebar mein **`🔌 MANUAL OTP LOGIN`** section dikhega.
3. Apne mobile (Google Authenticator ya Kite App) se **6-Digit OTP** dalo aur **`🔌 Connect with 6-Digit OTP`** button par click karo.
4. Success green message aate hi system trade execute karne ke liye taiyaar ho jayega.

### Option B: Automatic Login (Using KITE_TOTP_KEY)
1. Agar aapne `KITE_TOTP_KEY` ko `secrets.txt` mein sahi dalo hai, toh dashboard open karte hi automatic connect ho jayega.
2. Status bar mein check karo: **`LIVE`** aur **`ALGO ON`** green pills dikhni chahiye.

---

### Daily Checks:
1. Live positions dashboard par update ho rahi hain ya nahi check karo.
2. Telegram bot active hai ya nahi monitor karo.
3. All operations run on cloud VPS automatically.

