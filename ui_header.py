"""
ui_header.py — Master Command Header & Executive Matrix (Zerodha OS)
=====================================================================
Includes:
  1. Global 200 DMA Red Alert Watchdog Banner
  2. Master Safety Ribbon (Spot, P&L, Blocks, Legs, Algo Status, Heartbeat)
  3. Multi-Level Kill Switches & Emergency Panic Square-Off
  4. Executive Pod Status Matrix (M1–M4 Left | OS1–OS5 Right)
"""

from nicegui import ui
from typing import Callable, Dict, Any
import terminal_backend as tb
import db


def render_master_header(refresh_all_callback: Callable) -> Callable:
    """Renders the top executive command ribbon, 200 DMA alert, and pod matrix."""

    # ─────────────────────────────────────────────────────────────────────────
    # 1. GLOBAL 200 DMA RED ALERT BANNER (PERSISTENT WATCHDOG)
    # ─────────────────────────────────────────────────────────────────────────
    red_alert_container = ui.column().classes("w-full gap-0 p-0")

    def update_red_alert_banner():
        red_alert_container.clear()
        alert_info = tb.get_global_200dma_alert()
        if alert_info.get("active"):
            with red_alert_container:
                with ui.card().classes("w-full bg-[#3b0808] border-2 border-red-500 p-3 rounded-xl mb-3 flex flex-row items-center justify-between shadow-lg"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("warning", color="negative", size="2rem")
                        with ui.column().classes("gap-0"):
                            ui.label(f"🚨 200 DMA COLLATERAL BREACH ALERT: {alert_info['count']} Stocks Below 200 DMA!").classes("text-sm font-black text-red-300 tracking-wide")
                            ui.label(f"Breached Symbols: {alert_info['symbols_str']}").classes("text-xs text-red-100 font-semibold")
                    with ui.row().classes("items-center gap-2"):
                        ui.badge("PLEDGED EQUITY RISK", color="negative").classes("font-black text-xs px-2.5 py-1")

    update_red_alert_banner()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. 4-WIDGET MASTER COMMAND RIBBON
    # ─────────────────────────────────────────────────────────────────────────
    ribbon_card = ui.card().classes("trade-card w-full mb-3")

    with ribbon_card:
        with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
            # WIDGET 1: NIFTY 50 SPOT
            with ui.column().classes("gap-0 min-w-[140px]"):
                ui.label("NIFTY 50 SPOT").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                spot_lbl = ui.label("₹--,--").classes("mono text-2xl font-black text-amber-300")
                spot_sub = ui.label("Real-Time Kite Feed").classes("text-[10px] text-slate-400")

            # WIDGET 2: TOTAL PORTFOLIO P&L
            with ui.column().classes("gap-0 min-w-[160px]"):
                ui.label("TOTAL NET P&L (ALL BLOCKS)").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                pnl_lbl = ui.label("₹0.00").classes("mono text-2xl font-black text-emerald-400")
                pnl_sub = ui.label("Realized + MTM").classes("text-[10px] text-slate-400")

            # WIDGET 3: ACTIVE BLOCKS & LEGS
            with ui.column().classes("gap-0 min-w-[140px]"):
                ui.label("ACTIVE BLOCKS & OPEN LEGS").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                with ui.row().classes("items-baseline gap-2"):
                    blocks_lbl = ui.label("0").classes("mono text-2xl font-black text-sky-400")
                    ui.label("Blocks").classes("text-xs text-slate-400")
                    legs_lbl = ui.label("0").classes("mono text-lg font-bold text-slate-200")
                    ui.label("Open Legs").classes("text-xs text-slate-400")
                hedges_sub = ui.label("0 Hedges Active").classes("text-[10px] text-slate-400")

            # WIDGET 4: ALGO CONTROLLER & BROKER HEARTBEAT
            with ui.column().classes("gap-1 items-end min-w-[180px]"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("ALGO:").classes("text-xs font-bold text-slate-300")
                    algo_badge = ui.badge("ON", color="positive").classes("font-black text-xs px-2 py-0.5")

                    def _toggle_algo():
                        curr = db.get("algo_running", "ON") == "ON"
                        new_st = "OFF" if curr else "ON"
                        db.set("algo_running", new_st)
                        ui.notify(f"Algo Engine switched to {new_st}", type="info" if new_st == "ON" else "warning")
                        refresh_all_callback()
                    ui.button("TOGGLE", on_click=_toggle_algo).props("dense outline").classes("text-[10px] text-slate-300")

                with ui.row().classes("items-center gap-2 text-[10px] text-slate-400 mt-1"):
                    ui.icon("autorenew", size="14px", color="sky")
                    hb_lbl = ui.label("Heartbeat: --").classes("mono")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. EXECUTIVE POD STATUS MATRIX (M-UNITS LEFT | OS-UNITS RIGHT)
    # ─────────────────────────────────────────────────────────────────────────
    with ui.card().classes("trade-card w-full mb-4"):
        with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("view_module", color="sky", size="1.4rem")
                ui.label("EXECUTIVE POD MATRIX").classes("font-black text-sm text-white tracking-wide")
                ui.badge("V7.0 PARITY", color="primary").classes("text-[10px] font-bold")
            ui.label("Directional M-Units (Left) | Momentum OS-Units (Right)").classes("text-xs text-slate-400")

        pod_matrix_container = ui.row().classes("w-full gap-4")

    def update_pod_matrix():
        pod_matrix_container.clear()
        data = tb.get_executive_pod_matrix()
        m_pods = data.get("m_pods", [])
        os_pods = data.get("os_pods", [])

        with pod_matrix_container:
            # LEFT: Directional M-Units
            with ui.column().classes("flex-1 gap-2"):
                ui.label("🏛️ DIRECTIONAL M-UNITS (M1–M4)").classes("text-xs font-black text-sky-400 tracking-wider")
                with ui.grid(columns=2).classes("w-full gap-2"):
                    for p in m_pods:
                        uname = p["unit_name"]
                        anchor = p["anchor"]
                        reg = p["regime"]
                        pnl = p["net_pnl"]
                        has_act = p["has_active"]
                        reg_col = "text-emerald-400" if reg == "BULLISH" else "text-red-400"
                        bg_border = "border-emerald-500/40" if reg == "BULLISH" else "border-red-500/40"

                        with ui.card().classes(f"bg-[#0f141c] border {bg_border} p-2.5 rounded-lg"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(uname).classes("font-black text-xs text-white")
                                ui.badge(f"{'🟢' if reg == 'BULLISH' else '🔴'} {reg}", color="positive" if reg == "BULLISH" else "negative").classes("text-[9px] font-bold px-1.5")
                            ui.label(f"Anchor: ₹{anchor:,.1f} ({p['diff']:+,.1f})").classes("text-[10px] text-slate-300 mono mt-1")
                            with ui.row().classes("w-full justify-between items-center mt-1"):
                                ui.label("Pod P&L:").classes("text-[10px] text-slate-400")
                                ui.label(f"₹{pnl:+,.1f}").classes(f"text-xs font-black mono {'text-emerald-400' if pnl >= 0 else 'text-red-400'}")

            # RIGHT: Momentum OS-Units
            with ui.column().classes("flex-1 gap-2"):
                ui.label("🎯 MOMENTUM OS-UNITS (OS1–OS5)").classes("text-xs font-black text-amber-400 tracking-wider")
                with ui.grid(columns=3).classes("w-full gap-2"):
                    for p in os_pods:
                        uname = p["unit_name"]
                        has_act = p["has_active"]
                        is_lck = p["locked"]
                        pnl = p["net_pnl"]
                        stat_text = "LOCKED" if is_lck else ("ACTIVE" if has_act else "IDLE")
                        stat_col = "positive" if is_lck else ("primary" if has_act else "grey")

                        with ui.card().classes("bg-[#0f141c] border border-amber-900/40 p-2.5 rounded-lg"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(uname).classes("font-black text-xs text-white")
                                ui.badge(stat_text, color=stat_col).classes("text-[9px] font-bold px-1.5")
                            ui.label(f"P&L: ₹{pnl:+,.1f}").classes(f"text-[10px] font-bold mono mt-1 {'text-emerald-400' if pnl >= 0 else 'text-slate-400'}")
                            ui.label(f"Expiry: {p['expiry'] or 'None'}").classes("text-[9px] text-slate-400 truncate")

    update_pod_matrix()

    # ─────────────────────────────────────────────────────────────────────────
    # PERIODIC HEADER TELEMETRY REFRESH
    # ─────────────────────────────────────────────────────────────────────────
    def refresh_header_data():
        try:
            ribbon = tb.get_status_ribbon_data()
            spot_lbl.set_text(f"₹{ribbon['live_spot']:,.2f}")

            pnl_val = ribbon["total_pnl"]
            pnl_lbl.set_text(f"₹{pnl_val:+,.2f}")
            pnl_lbl.classes(replace=f"mono text-2xl font-black {'text-emerald-400' if pnl_val >= 0 else 'text-red-400'}")

            blocks_lbl.set_text(str(ribbon["n_blocks"]))
            legs_lbl.set_text(str(ribbon["n_open_strikes"]))
            hedges_sub.set_text(f"{ribbon['n_hedges']} Hedges Active")

            algo_on = ribbon["algo_running"]
            algo_badge.set_text("ON" if algo_on else "OFF")
            algo_badge.props(f"color={'positive' if algo_on else 'negative'}")

            hb_lbl.set_text(f"Heartbeat: {ribbon['token_countdown']}")

            update_red_alert_banner()
            update_pod_matrix()
        except Exception:
            pass

    return refresh_header_data
