"""
ui_equity.py — Equity & Gold 200 DMA Monitor (Zerodha OS)
=========================================================
Tab 6:
  • Portfolio Collateral Holdings Summary
  • Emergency Red Alert Watchlist (LTP < 200 DMA)
  • Full Holdings Table (Equity, Gold, Liquid)
  • Manual Kite Sync & 200 DMA Recalculate Actions
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb


def render_equity_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 6: Equity & Gold (200 DMA Monitor)."""

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-purple-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("📊 EQUITY & GOLD (200 DMA MONITOR)").classes("font-black text-base text-white tracking-wide")
                    ui.label("Long-Term Collateral & Pledged Holdings • 200 Days Moving Average Audit • Gold/Liquid Exemptions").classes("text-xs text-slate-400")

                with ui.row().classes("items-center gap-2"):
                    def _sync():
                        res = tb.sync_equity_holdings_from_kite()
                        ui.notify(res.get("message"), type="info")
                        render_eq_view()
                        refresh_all_callback()
                    ui.button("🔄 SYNC KITE HOLDINGS", on_click=_sync).classes("bg-purple-700 hover:bg-purple-600 text-white font-bold text-xs")

                    def _recalc():
                        res = tb.recalculate_all_200dma()
                        ui.notify(res.get("message"), type="positive")
                        render_eq_view()
                        refresh_all_callback()
                    ui.button("⚡ RECALC 200 DMA", on_click=_recalc).classes("bg-slate-700 hover:bg-slate-600 text-amber-300 font-bold text-xs")

        eq_view_container = ui.column().classes("w-full gap-4")

    def render_eq_view():
        eq_view_container.clear()
        analysis = tb.get_equity_200dma_cockpit_data()
        results = analysis.get("results", [])
        red_alerts = analysis.get("red_alerts", [])
        tot_inv = analysis.get("total_invested", 0.0)
        tot_cur = analysis.get("total_current", 0.0)
        green_cnt = analysis.get("green_count", 0)
        red_cnt = analysis.get("red_count", 0)

        with eq_view_container:
            # ── 1. PORTFOLIO COLLATERAL SUMMARY RIBBON ──
            with ui.row().classes("w-full gap-4 flex-wrap"):
                with ui.card().classes("trade-card flex-1 min-w-[200px] p-3"):
                    ui.label("TOTAL COLLATERAL VALUE").classes("text-[10px] text-slate-400 font-bold")
                    ui.label(f"₹{tot_cur:,.2f}").classes("mono text-xl font-black text-white mt-0.5")
                    ui.label(f"Invested: ₹{tot_inv:,.2f}").classes("text-[10px] text-slate-400")

                with ui.card().classes("trade-card flex-1 min-w-[200px] p-3"):
                    ui.label("TOTAL NET GAIN / LOSS").classes("text-[10px] text-slate-400 font-bold")
                    gain = tot_cur - tot_inv
                    g_pct = (gain / tot_inv * 100) if tot_inv > 0 else 0
                    ui.label(f"₹{gain:+,.2f} ({g_pct:+.1f}%)").classes(f"mono text-xl font-black mt-0.5 {'text-emerald-400' if gain >= 0 else 'text-red-400'}")

                with ui.card().classes("trade-card flex-1 min-w-[160px] p-3"):
                    ui.label("STOCKS ABOVE 200 DMA").classes("text-[10px] text-slate-400 font-bold")
                    ui.label(f"🟢 {green_cnt} SAFE").classes("mono text-xl font-black text-emerald-400 mt-0.5")

                with ui.card().classes("trade-card flex-1 min-w-[160px] p-3"):
                    ui.label("STOCKS BELOW 200 DMA").classes("text-[10px] text-slate-400 font-bold")
                    ui.label(f"🔴 {red_cnt} ALERT").classes(f"mono text-xl font-black mt-0.5 {'text-red-400 font-black' if red_cnt > 0 else 'text-slate-400'}")

            # ── 2. EMERGENCY RED ALERT WATCHLIST ──
            if red_alerts:
                with ui.card().classes("w-full bg-[#2a0808] border-2 border-red-500 p-4 rounded-xl mt-2"):
                    with ui.row().classes("w-full justify-between items-center border-b border-red-900 pb-2 mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("report_problem", color="negative", size="1.4rem")
                            ui.label(f"CRITICAL RED ALERTS: {len(red_alerts)} STOCKS BELOW 200 DMA").classes("font-black text-sm text-red-300")
                        ui.badge("ACTION REQUIRED", color="negative").classes("font-black text-xs px-2 py-0.5")

                    with ui.grid(columns=3).classes("w-full gap-3"):
                        for r in red_alerts:
                            with ui.card().classes("bg-[#180a0a] border border-red-800/60 p-3 rounded-lg"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    ui.label(r.get("symbol", "")).classes("font-black text-sm text-white")
                                    gap_pct = r.get("gap_pct", 0)
                                    ui.badge(f"{gap_pct:+.1f}%", color="negative").classes("font-bold text-xs")
                                ui.label(f"LTP: ₹{r.get('ltp', 0):,.2f} | 200 DMA: ₹{r.get('dma_200', 0):,.2f}").classes("mono text-xs text-red-300 mt-1")
                                ui.label(f"Gap: ₹{r.get('gap', 0):,.2f}").classes("text-[10px] text-slate-400")

            # ── 3. FULL HOLDINGS AUDIT TABLE ──
            with ui.card().classes("trade-card w-full p-4 mt-2"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    ui.label("📋 FULL HOLDINGS & 200 DMA HEALTH TABLE").classes("font-black text-sm text-white")
                    ui.label(f"{len(results)} Total Assets Monitored").classes("text-xs text-slate-400")

                if not results:
                    ui.label("No stored holdings in database. Click 'Sync Kite Holdings' above to download.").classes("text-xs text-slate-500 italic py-4 text-center")
                else:
                    for item in results:
                        sym = item.get("symbol", "")
                        cat = item.get("category", "EQUITY")
                        ltp_val = item.get("ltp", 0.0)
                        dma_val = item.get("dma_200", 0.0)
                        diff_val = item.get("dma_diff", 0.0)
                        diff_pct = item.get("dma_diff_pct", 0.0)
                        sig = item.get("signal", "GREEN")

                        if cat == "GOLD":
                            badge_text, badge_col = "🟡 GOLD (EXEMPT)", "warning"
                        elif cat == "LIQUID":
                            badge_text, badge_col = "💧 LIQUID (EXEMPT)", "primary"
                        elif sig == "RED":
                            badge_text, badge_col = "🔴 BELOW 200 DMA", "negative"
                        else:
                            badge_text, badge_col = "🟢 ABOVE 200 DMA", "positive"

                        with ui.row().classes("w-full justify-between items-center py-2 border-b border-slate-800 text-xs text-slate-200"):
                            with ui.row().classes("items-center gap-3"):
                                ui.label(sym).classes("font-bold text-white mono text-xs w-32")
                                ui.badge(badge_text, color=badge_col).classes("text-[10px] font-bold")

                            with ui.row().classes("items-center gap-6 mono"):
                                ui.label(f"LTP: ₹{ltp_val:,.2f}").classes("text-slate-300")
                                ui.label(f"200 DMA: ₹{dma_val:,.2f}").classes("text-amber-300" if dma_val > 0 else "text-slate-500")
                                if cat not in ("GOLD", "LIQUID"):
                                    ui.label(f"Gap: {diff_pct:+.1f}%").classes(f"font-bold {'text-emerald-400' if diff_val >= 0 else 'text-red-400'}")

    render_eq_view()
    return render_eq_view
