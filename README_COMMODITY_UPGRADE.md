# 🛢️ MCX Commodity Engine Upgrade — README

## What This Does
Adds the **MCX Commodity Futures Engine** to your existing Zerodha OS installation.
- Trades MCX commodities (Gold, Silver, Crude Oil, Copper, Nickel, etc.)
- Uses an Anchor Price strategy: goes LONG when price is above anchor, SHORT when below
- Evaluates on 15-minute candle boundaries
- Auto square-off at 11:00 PM IST (intraday)
- Completely isolated from your Option Selling engine

## What's Inside
| File | Purpose |
|---|---|
| `commodity_engine.py` | MCX trading engine (runs as separate service) |
| `commodity_executor.py` | Order execution layer for MCX contracts |
| `upgrade_add_commodity.py` | Auto-patches your existing files to add commodity support |

## How to Install

### Step 1: Copy Files
Copy all 3 files into your `ZERODHA-OS/` directory (same folder as `app.py`).

### Step 2: Run Upgrade Script
```bash
cd /root/BHARAT-SYSTEMS/ZERODHA-OS
python3 upgrade_add_commodity.py
```
This will:
- ✅ Backup your existing files (creates `.backup_YYYYMMDD` copies)
- ✅ Add commodity config to `config.py`
- ✅ Add commodity database keys to `db.py`
- ✅ Add MCX functions to `kite_executor.py`
- ✅ Add commodity tab to `app.py`
- ❌ Will NOT touch `secrets.txt`, your database, or existing trading logic

### Step 3: Set Up Systemd Service
Create the service file on VPS:
```bash
cat > /etc/systemd/system/zerodha_commodity.service << 'EOF'
[Unit]
Description=Zerodha Commodity Futures Engine
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/BHARAT-SYSTEMS/ZERODHA-OS
ExecStart=/usr/bin/python3 -u commodity_engine.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zerodha_commodity.service
```

### Step 4: Restart Services
```bash
systemctl restart zerodha_engine zerodha_commodity zerodha_dashboard
```

### Step 5: Use the Dashboard
1. Open your dashboard URL
2. Go to the **"🛢️ MCX Commodities FUT"** tab
3. Select a commodity (e.g. GOLDPETAL)
4. Set the Anchor Price
5. Toggle the engine ON

## ⚠️ Important Notes
- This upgrade does NOT modify your credentials or VPS settings
- Your existing Option Selling engine continues to work independently
- MCX market hours: 9:00 AM to 11:30 PM IST
- Auto square-off: 11:00 PM IST (configurable)
