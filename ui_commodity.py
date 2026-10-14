"""
ui_commodity.py — MCX Commodity Futures Engine (Zerodha OS)
===========================================================
Tab 5:
  • Commodity Engine Status & Auto-Trade Toggle
  • Active Contract Selector (Crude Oil, Natural Gas, Gold, Silver, Metals)
  • Live MCX LTP & Position Tracking (FLAT / LONG / SHORT)
  • 1-Click Margin-Safe Position Square-Off
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb
import db


def render_commodity_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 5: MCX Commodities FUT Engine."""

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-orange-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("🛢️ MCX COMMODITY FUTURES ENGINE").classes("font-black text-base text-white tracking-wide")
                    ui.label("15-Minute Candle Closed Boundaries • Auto Bracket Orders • Trailing SL & Targets").classes("text-xs text-slate-400")
                ui.badge("MCX ENGINE", color="warning").classes("text-xs font-bold px-2 py-1")

        comm_view_container = ui.column().classes("w-full gap-4")

    def render_comm_view():
        comm_view_container.clear()
        data = tb.get_commodity_cockpit_data()
        is_running = data["running"]
        pos_state = data["position_state"]
        selected_contract = data["selected_contract"]
        live_ltp = data["live_ltp"]
        live_pnl = data["live_pnl"]
        positions = data["positions"]

        with comm_view_container:
            # ── 1. ENGINE STATUS BAR & TOGGLE ──
            with ui.card().classes("trade-card w-full p-4"):
                with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label("ENGINE STATUS:").classes("text-xs font-bold text-slate-400")
                        ui.badge("🟢 RUNNING & MONITORING" if is_running else "⚪ PAUSED / OFF", color="positive" if is_running else "grey").classes("font-black text-xs px-3 py-1")

                        def _toggle_comm():
                            res = tb.toggle_commodity_engine(not is_running)
                            ui.notify(res.get("message"), type="info")
                            render_comm_view()
                            refresh_all_callback()
                        ui.button("TOGGLE ENGINE", on_click=_toggle_comm).props("dense outline").classes("text-xs text-slate-300")

                    with ui.row().classes("items-center gap-3"):
                        asset_opts = list(data.get("assets_list", []))
                        sel_val = selected_contract
                        if sel_val and sel_val not in asset_opts:
                            asset_opts.insert(0, sel_val)
                        elif not sel_val and asset_opts:
                            sel_val = asset_opts[0]
                        contract_select = ui.select(label="Target Asset", options=asset_opts, value=sel_val).classes("w-48")
                        def _set_contract():
                            db.set("comm_selected_contract", str(contract_select.value))
                            ui.notify(f"Selected Commodity: {contract_select.value}", type="info")
                            render_comm_view()
                            refresh_all_callback()
                        ui.button("SELECT", on_click=_set_contract).classes("bg-orange-600 text-white font-bold text-xs")

            # ── 2. LIVE POSITION STATE CARD ──
            with ui.card().classes("trade-card w-full p-4 mt-2"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("show_chart", color="orange", size="1.4rem")
                        ui.label(f"ACTIVE CONTRACT: {selected_contract}").classes("font-black text-sm text-white")
                    ui.badge(pos_state, color="positive" if pos_state == "LONG" else ("negative" if pos_state == "SHORT" else "grey")).classes("font-black text-xs px-2.5 py-1")

                with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
                    with ui.column().classes("gap-0"):
                        ui.label("MCX LIVE LTP").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"₹{live_ltp:,.2f}" if live_ltp > 0 else "Offline / Waiting").classes("mono text-2xl font-black text-amber-300")

                    with ui.column().classes("gap-0"):
                        ui.label("ENTRY PRICE").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"₹{data['entry_price']:,.2f}" if data['entry_price'] > 0 else "None").classes("mono text-2xl font-black text-slate-200")

                    with ui.column().classes("gap-0"):
                        ui.label("LIVE P&L").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"₹{live_pnl:+,.2f}").classes(f"mono text-2xl font-black {'text-emerald-400' if live_pnl >= 0 else 'text-red-400'}")

                if pos_state != "FLAT":
                    with ui.row().classes("w-full justify-end mt-4"):
                        def _sq_comm():
                            res = tb.square_off_commodity_position()
                            ui.notify(res.get("message"), type="warning")
                            render_comm_view()
                            refresh_all_callback()
                        ui.button("🚨 Square Off MCX Position", on_click=_sq_comm).classes("bg-red-600 hover:bg-red-700 text-white font-black text-xs px-4 py-2 rounded-lg")

            # ── 3. BROKER POSITIONS LIST ──
            if positions:
                with ui.card().classes("trade-card w-full p-4 mt-2"):
                    ui.label("📋 BROKER MCX POSITIONS").classes("font-black text-sm text-white mb-2")
                    for p in positions:
                        with ui.row().classes("w-full justify-between py-1.5 border-b border-slate-800 text-xs text-slate-300"):
                            ui.label(f"{p.get('tradingsymbol')} ({p.get('product')})").classes("font-bold text-white mono")
                            ui.label(f"Qty: {p.get('quantity')} | P&L: ₹{p.get('pnl', 0):,.2f}").classes("mono text-emerald-400")
            else:
                with ui.card().classes("trade-card w-full p-6 text-center mt-2 items-center"):
                    ui.icon("check_circle", color="positive", size="2.5rem")
                    ui.label("No Open Commodity Positions in Broker Account").classes("text-sm font-bold text-slate-300 mt-2")
                    ui.label("Engine is tracking 15m closed candle boundaries for the next breakout trigger.").classes("text-xs text-slate-500 mt-0.5")

    render_comm_view()
    return render_comm_view
