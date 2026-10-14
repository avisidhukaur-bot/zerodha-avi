# 🔬 Forensic Root Cause Analysis & Progressive Web App (PWA) Architecture Plan
_Date: 05-Oct-2026 | System: Zerodha OS Option Selling Console (Port 9007 / Port 80)_

---

## 1. 🔍 ROOT CAUSE ANALYSIS: Why did Port 9007 stop loading?

### Root Cause 1: Streamlit WebSocket CORS & XSRF Security Conflict
* **Mechanism:** Streamlit communicates between the Python server and the browser via real-time WebSockets.
* **The Conflict:** In `/root/.streamlit/config.toml`, `enableXsrfProtection = true` was enabled alongside `enableCORS = false`. Streamlit flagged this incompatibility and forced `enableCORS = true`.
* **The Symptom:** When any external mobile browser (e.g. Chrome on Android) or remote IP accessed `http://5.75.250.104:9007`, Streamlit's WebSocket security rejected the cross-origin connection, causing the page to hang indefinitely on a **dark blank/black screen**.

### Root Cause 2: Cellular ISP Port Filtering (Jio / Airtel vs Custom Port 9007)
* **Mechanism:** Mobile operators (Jio 4G/5G, Airtel) filter or drop non-standard high ports (like `:9007`) on raw HTTP traffic to prevent malware/botnets.
* **The Symptom:** Browsers on mobile data experienced `ERR_CONNECTION_TIMED_OUT` when attempting to reach `:9007`, whereas standard web ports (`80` / `443`) are never filtered.

### Root Cause 3: Zerodha Kite Connect Static IP Whitelisting Invariant
* **Mechanism:** Zerodha enforces strict static IP whitelisting for all order placement API requests.
* **The Whitelisted IP:** `5.75.250.104` (German Cloud VPS).
* **The Issue:** Attempting to execute trades from the home broadband laptop (`139.5.1.170`) was rejected by Zerodha (`IP not allowed`). All trade executions must originate from the VPS (`5.75.250.104`).

---

## 2. 🛠️ THE ARCHITECTURAL SOLUTION (Why Nginx Reverse Proxy Fixes This Permanently)

```
[ Mobile Phone / PC Browser ]
             │
      Standard Port 80 (HTTP) / Port 443 (HTTPS)
             ▼
     [ Nginx Web Server ] (Reverse Proxy on VPS 5.75.250.104)
             │
   Internal Loopback (127.0.0.1:9007 with WebSocket Upgrade)
             ▼
[ Streamlit App & Trading Engine (main.py) ]
             │
   Whitelisted IP (5.75.250.104)
             ▼
 [ Zerodha Kite Connect API & NSE Exchange ]
```

1. **Standard Port Routing:** Moving from `:9007` to Port `80/443` eliminates all ISP and firewall blocking.
2. **WebSocket Proxying:** Nginx properly forwards `Upgrade` and `Connection` headers to Streamlit, eliminating the black blank screen issue.
3. **Execution Integrity:** Zerodha orders execute exclusively through the whitelisted VPS IP (`5.75.250.104`).

---

## 3. 📱 PROGRESSIVE WEB APP (PWA) IMPLEMENTATION PLAN

To turn the Zerodha Option Selling console into an installable **PWA (Progressive Web App)** on Android, iOS, and Laptop:

### Step 1: Web App Manifest (`manifest.json`)
* Configures the app name ("Zerodha OS"), icons, theme color (`#0f172a`), background color, and `display: "standalone"`.
* Allows users to tap **"Add to Home screen"** on Chrome/Safari to install it like a native Android/iOS app with no browser address bar.

### Step 2: Service Worker (`sw.js`)
* Manages offline fallback, caching of static UI components (CSS, fonts, logos), and auto-reconnecting WebSocket links.

### Step 3: HTTPS & SSL Certificate
* PWAs require HTTPS (Secure Context) for Service Workers.
* We configure a free Let's Encrypt SSL certificate or domain mapping for automated 1-click install prompts.
