"""
terminal_app.py — Next-Gen Lightweight Trading Console (Zerodha OS)
===================================================================
Version: V7.0 (Production Edition — 100% Full Feature Parity)
Port: 9009 (Public Access Buffer Port)
Tech: NiceGUI 3.x, FastAPI, Uvicorn, WebSocket Reactive Architecture
Design: Institutional Dark Theme (TradingView / Bloomberg Style)

Modular Brick Composition:
  • ui_header.py    -- Master Command Ribbon, Emergency Shutdown, Pod Matrix, 200 DMA Alert
  • ui_m_units.py   -- Tab 1: Directional M-Units Cockpit (M1–M4)
  • ui_os_units.py  -- Tab 2: Momentum OS-Units Cockpit (OS1–OS5)
  • ui_weekly_st.py -- Tab 3: Weekly ST-2H Cockpit (W1 — V7.5 Master Edition)
  • ui_blocks.py    -- Tab 4: Active Expiry Blocks & Live Positions
  • ui_commodity.py -- Tab 5: MCX Commodities FUT Engine
  • ui_equity.py    -- Tab 6: Equity & Gold (200 DMA Monitor)
  • ui_logs.py      -- Tab 7: Order History & Real-Time Audit Logs
"""

import os
import sys
import argparse
from datetime import datetime
import pytz
from fastapi.responses import FileResponse, Response
from nicegui import ui, app

# Force UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import terminal_backend as tb
import config as cfg

# UI Bricks
import ui_header
import ui_m_units
import ui_os_units
import ui_weekly_st
import ui_blocks
import ui_commodity
import ui_equity
import ui_logs

IST = pytz.timezone("Asia/Kolkata")

# Parse CLI arguments
parser = argparse.ArgumentParser(description="Zerodha Option Selling Trading Terminal V7.0")
parser.add_argument("--port", type=int, default=9009, help="Web port (default: 9009)")
parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
args, _ = parser.parse_known_args()

# ─────────────────────────────────────────────────────────────────────────────
# PWA & STATIC ASSET ROUTING (FASTAPI)
# ─────────────────────────────────────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.add_static_files("/static", STATIC_DIR)


@app.get("/manifest.json")
def pwa_manifest():
    mf_path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(mf_path):
        return FileResponse(mf_path, media_type="application/manifest+json")
    return Response(content="{}", media_type="application/manifest+json")


@app.get("/sw.js")
def pwa_service_worker():
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return Response(content="", media_type="application/javascript")


# Custom Institutional CSS
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap');

body {
    font-family: 'Inter', -apple-system, sans-serif !important;
    background-color: #0b0e14 !important;
    color: #e2e8f0 !important;
    margin: 0;
    padding: 0;
}

.mono {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Glassmorphism Cards */
.trade-card {
    background: #151a23 !important;
    border: 1px solid #232d3f !important;
    border-radius: 12px !important;
    padding: 16px !important;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5) !important;
}

/* Institutional Tab Styling */
.q-tab {
    font-weight: 700 !important;
    letter-spacing: 0.4px !important;
    font-size: 0.82rem !important;
}

.q-tabs {
    background: #0f141c !important;
    border-bottom: 2px solid #1e293b !important;
}

.q-tab--active {
    color: #38bdf8 !important;
    background: #151d2a !important;
}
"""

PWA_HEAD_HTML = """
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0b0e14">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Zerodha V7">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/static/icon-512.png">

<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js')
        .then(reg => console.log('[PWA] ServiceWorker registered with scope:', reg.scope))
        .catch(err => console.error('[PWA] ServiceWorker registration failed:', err));
    });
  }

  window.deferredInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    window.deferredInstallPrompt = e;
    console.log('[PWA] beforeinstallprompt captured!');
  });

  window.triggerPWAInstall = function() {
    if (window.deferredInstallPrompt) {
      window.deferredInstallPrompt.prompt();
      window.deferredInstallPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('[PWA] User installed the app');
        }
        window.deferredInstallPrompt = null;
      });
    } else {
      alert("📲 Chrome PWA Installation Instructions:\\n\\n" +
            "1. In Chrome, click the 3 dots (top-right menu) ➔ 'Install Zerodha OS Trading Console...' (or 'Add to Home Screen').\\n\\n" +
            "2. Note on HTTP/IP Security:\\n" +
            "Chrome requires origins to be secure for 1-click install.\\n" +
            "If install is disabled, open a new tab to:\\n" +
            "chrome://flags/#unsafely-treat-insecure-origin-as-secure\\n" +
            "➔ Add: http://46.224.133.16:9009\\n" +
            "➔ Select 'Enabled' & click 'Relaunch'.\\n" +
            "Then the Install icon will immediately appear in your address bar!");
    }
  };
</script>
"""

ui.add_head_html(f"<style>{CUSTOM_CSS}</style>\n{PWA_HEAD_HTML}", shared=True)


@ui.page("/")
def main_page():
    ui.dark_mode().enable()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. TOP STICKY APPLICATION BAR
    # ─────────────────────────────────────────────────────────────────────────
    with ui.header().classes("bg-[#0f141c] border-b border-[#232d3f] px-6 py-2.5 flex items-center justify-between shadow-lg sticky top-0 z-50"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("bolt", color="amber", size="2.2rem")
            with ui.column().classes("gap-0"):
                ui.label("ZERODHA OS TRADING CONSOLE V7.0").classes("text-base font-black tracking-wide text-white")
                ui.label("PORT 9009 | HIGH-FREQUENCY WEBSOCKET LINK | PARALLEL SAFE DEPLOYMENT").classes("text-[10px] font-bold text-sky-400 tracking-wider")

        with ui.row().classes("items-center gap-3"):
            # Live Spot Header Badge
            with ui.row().classes("items-center gap-1.5 bg-[#1a2230] border border-[#2d3a4f] py-1 px-3 rounded-lg"):
                ui.label("SPOT:").classes("text-[10px] font-bold text-slate-400")
                top_spot_lbl = ui.label("₹--,--").classes("mono text-sm font-black text-amber-300")

            # Broker Health Badge
            top_broker_badge = ui.badge("Checking...", color="grey").classes("font-bold text-[11px] px-2.5 py-1 rounded")

            # PWA Install Button
            ui.button("📲 INSTALL APP", on_click=lambda: ui.run_javascript("window.triggerPWAInstall()")).props("dense outline").classes("bg-[#1a2936] text-sky-300 border border-sky-500/50 hover:bg-sky-900/50 font-bold px-2.5 py-1 rounded-lg text-xs tracking-wider")

            # Global Emergency Panic Kill Button
            def _open_panic_dialog():
                with ui.dialog() as panic_dlg, ui.card().classes("bg-[#280c0c] border-2 border-red-500 p-6 rounded-xl max-w-lg"):
                    ui.label("🚨 GLOBAL EMERGENCY PANIC SQUARE OFF").classes("text-lg font-black text-red-400")
                    ui.label("Are you 100% sure you want to SQUARE OFF ALL open positions across M-Units, OS-Units, Weekly ST, and MCX Commodities?").classes("text-slate-200 text-xs font-semibold mt-2")
                    ui.label("This will immediately send market orders to Zerodha Kite to square off every single active trade!").classes("text-xs text-red-300 font-bold mt-1")

                    with ui.row().classes("w-full justify-end gap-3 mt-6"):
                        ui.button("CANCEL", on_click=panic_dlg.close).classes("bg-slate-700 text-white font-bold text-xs")
                        def _confirm_panic():
                            panic_dlg.close()
                            res = tb.emergency_square_off_all()
                            if res.get("ok"):
                                ui.notify(res.get("message"), type="negative", position="top", close_button="OK", timeout=10000)
                            else:
                                ui.notify(f"Kill failed: {res.get('message')}", type="warning", position="top")
                            refresh_all_telemetry()
                        ui.button("YES, SQUARE OFF ALL NOW", on_click=_confirm_panic).classes("bg-red-600 hover:bg-red-700 text-white font-black text-xs px-4 py-2")
                panic_dlg.open()

            ui.button("🚨 PANIC KILL ALL", on_click=_open_panic_dialog).classes("bg-red-600 hover:bg-red-700 text-white font-black px-3.5 py-1.5 rounded-lg text-xs tracking-wider shadow-md")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. MAIN WORKSPACE CONTAINER
    # ─────────────────────────────────────────────────────────────────────────
    with ui.column().classes("w-full p-4 lg:p-6 gap-4 max-w-[1750px] mx-auto"):

        # ── BRICK 1: MASTER COMMAND HEADER, 200 DMA WATCHDOG & POD MATRIX ──
        update_header_fn = ui_header.render_master_header(lambda: refresh_all_telemetry())

        # ── 7-TAB CLEAN SEPARATION ARCHITECTURE ──
        with ui.tabs().classes("w-full rounded-t-xl overflow-hidden shadow") as tabs:
            tab_m = ui.tab("🏛️ Directional M-Units (M1–M4)")
            tab_os = ui.tab("🎯 Momentum OS-Units (OS1–OS5)")
            tab_wst = ui.tab("⚡ Weekly ST-2H Cockpit (W1)")
            tab_blk = ui.tab("📦 Active Expiry Blocks & Positions")
            tab_comm = ui.tab("🛢️ MCX Commodities FUT")
            tab_eq = ui.tab("📊 Equity & Gold (200 DMA Monitor)")
            tab_log = ui.tab("📜 Order History & Audit Logs")

        with ui.tab_panels(tabs, value=tab_m).classes("w-full bg-transparent"):
            # TAB 1: DIRECTIONAL M-UNITS (M1–M4)
            with ui.tab_panel(tab_m).classes("p-0 pt-4"):
                render_m_fn = ui_m_units.render_m_units_tab(lambda: refresh_all_telemetry())

            # TAB 2: MOMENTUM OS-UNITS (OS1–OS5)
            with ui.tab_panel(tab_os).classes("p-0 pt-4"):
                render_os_fn = ui_os_units.render_os_units_tab(lambda: refresh_all_telemetry())

            # TAB 3: WEEKLY ST-2H COCKPIT (W1)
            with ui.tab_panel(tab_wst).classes("p-0 pt-4"):
                render_wst_fn = ui_weekly_st.render_weekly_st_tab(lambda: refresh_all_telemetry())

            # TAB 4: ACTIVE EXPIRY BLOCKS & LIVE POSITIONS
            with ui.tab_panel(tab_blk).classes("p-0 pt-4"):
                render_blk_fn = ui_blocks.render_blocks_tab(lambda: refresh_all_telemetry())

            # TAB 5: MCX COMMODITIES FUT ENGINE
            with ui.tab_panel(tab_comm).classes("p-0 pt-4"):
                render_comm_fn = ui_commodity.render_commodity_tab(lambda: refresh_all_telemetry())

            # TAB 6: EQUITY & GOLD (200 DMA MONITOR)
            with ui.tab_panel(tab_eq).classes("p-0 pt-4"):
                render_eq_fn = ui_equity.render_equity_tab(lambda: refresh_all_telemetry())

            # TAB 7: ORDER HISTORY & REAL-TIME AUDIT LOGS
            with ui.tab_panel(tab_log).classes("p-0 pt-4"):
                render_log_fn = ui_logs.render_logs_tab(lambda: refresh_all_telemetry())

        # ─────────────────────────────────────────────────────────────────────
        # FOOTER
        # ─────────────────────────────────────────────────────────────────────
        with ui.card().classes("w-full bg-[#0a0d14] border border-[#1e293b] p-4 rounded-xl mt-6 items-center"):
            with ui.row().classes("w-full justify-between items-center text-xs text-slate-400"):
                ui.label("⚡ ZERODHA OPTION SELLING ENGINE V7.0 | ULTRA-LIGHTWEIGHT NICEGUI TERMINAL").classes("font-bold text-slate-300")
                ui.label("PORT 9009 | SYSTEM STATUS: 🟢 OPTIMIZED | VPS: 46.224.133.16").classes("mono text-slate-400")

    # ─────────────────────────────────────────────────────────────────────────
    # PERIODIC TELEMETRY LOOP (REACTIVE WEBSOCKET BINDING)
    # ─────────────────────────────────────────────────────────────────────────
    def refresh_all_telemetry():
        try:
            spot = tb.get_live_spot()
            top_spot_lbl.set_text(f"₹{spot:,.2f}")

            # Top Broker Badge
            b_st = tb.get_broker_status()
            top_broker_badge.set_text(b_st["status_text"])
            top_broker_badge.props(f"color={b_st['badge_color']}")

            # Update Header Telemetry
            if callable(update_header_fn):
                update_header_fn()
        except Exception:
            pass

    # Initial trigger
    refresh_all_telemetry()

    # Native WebSocket reactive timer: 2 seconds interval
    ui.timer(2.0, refresh_all_telemetry)


if __name__ in {"__main__", "__mp_main__"}:
    print(f"[NICEGUI] Starting Zerodha Next-Gen Console V7.0 on {args.host}:{args.port}...")
    ui.run(
        host=args.host,
        port=args.port,
        title="Zerodha OS Next-Gen Trading Console V7.0",
        favicon="⚡",
        dark=True,
        reload=False,
        show=False
    )
