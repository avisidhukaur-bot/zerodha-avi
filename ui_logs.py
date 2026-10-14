"""
ui_logs.py — Order History & Real-Time Audit Logs (Zerodha OS)
=============================================================
Tab 7:
  • Category Filter Pills (ALL, ORDERS, EXITS, SL_SENTINEL, COMMODITY, EQUITY_200DMA, WARN, ERROR)
  • Real-Time Log Streamer
  • Search filter
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb


def render_logs_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 7: Order History & Real-Time Audit Logs."""

    active_category = {"val": "ALL"}
    search_query = {"val": ""}

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-slate-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("📜 ORDER HISTORY & REAL-TIME AUDIT LOGS").classes("font-black text-base text-white tracking-wide")
                    ui.label("Real-Time Telemetry Stream • Category Filters • Execution Ground-Truth").classes("text-xs text-slate-400")
                ui.badge("LIVE LOG STREAM", color="primary").classes("text-xs font-bold px-2 py-1")

        # Category Filter Pills
        categories = ["ALL", "ORDERS", "EXITS", "SL_SENTINEL", "COMMODITY", "EQUITY_200DMA", "WARN", "ERROR"]
        with ui.row().classes("w-full gap-2 items-center bg-[#0f141c] p-2.5 rounded-xl border border-[#232d3f] flex-wrap"):
            ui.label("FILTER CATEGORY:").classes("text-xs font-black text-slate-400 ml-1")
            cat_buttons = {}
            for cat in categories:
                def _make_cat_click(c=cat):
                    def _filter():
                        active_category["val"] = c
                        for k, btn in cat_buttons.items():
                            if k == c:
                                btn.classes(replace="bg-sky-600 text-white font-black text-xs px-2.5 py-1 shadow")
                            else:
                                btn.classes(replace="bg-[#1a2230] text-slate-300 font-bold text-xs px-2.5 py-1")
                        render_logs_view()
                    return _filter
                btn = ui.button(cat, on_click=_make_cat_click(cat)).classes("bg-[#1a2230] text-slate-300 font-bold text-xs px-2.5 py-1 rounded-lg")
                cat_buttons[cat] = btn
            cat_buttons["ALL"].classes(replace="bg-sky-600 text-white font-black text-xs px-2.5 py-1 shadow")

            # Search bar
            search_input = ui.input(placeholder="Search logs...", on_change=lambda e: _on_search(e.value)).classes("w-60 ml-auto").props("dense outlined")
            def _on_search(val):
                search_query["val"] = (val or "").strip().lower()
                render_logs_view()

        logs_container = ui.column().classes("w-full gap-1")

    def render_logs_view():
        logs_container.clear()
        cat = active_category["val"]
        q = search_query["val"]
        raw_logs = tb.get_audit_logs(category=cat, limit=120)

        if q:
            raw_logs = [l for l in raw_logs if q in l["raw"].lower()]

        with logs_container:
            with ui.card().classes("w-full bg-[#07090e] border border-slate-800 p-3 rounded-xl max-h-[600px] overflow-y-auto mono text-xs"):
                if not raw_logs:
                    ui.label("No log entries match the current category / search filter.").classes("text-slate-500 italic py-6 text-center")
                else:
                    for l in raw_logs:
                        with ui.row().classes("w-full items-start gap-2 py-0.5 border-b border-slate-900/60 leading-relaxed"):
                            ui.badge(l["level"], color="dark").classes("text-[9px] font-bold px-1.5 py-0")
                            ui.label(l["raw"]).classes(f"flex-1 {l['color_class']} break-all")

    render_logs_view()
    return render_logs_view
