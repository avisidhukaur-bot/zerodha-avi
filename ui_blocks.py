"""
ui_blocks.py — Active Expiry Blocks & Live Positions (Zerodha OS)
=================================================================
Tab 4:
  • Rich Block Cards (M-Units, OS-Units, Weekly Spreads)
  • Dedicated Unit Master Anchor Controller
  • CE & PE Split Leg Tables with Individual 1-Click Close
  • Sweep Orphan Hedges Controller
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb
import config as cfg


def render_blocks_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 4: Active Expiry Blocks & Live Positions."""

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-sky-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("📦 ACTIVE EXPIRY BLOCKS & LIVE POSITIONS").classes("font-black text-base text-white tracking-wide")
                    ui.label("CE / PE Split Leg Tables • Master Anchor Modifiers • 1-Click Margin-Safe Leg Close • Hedge Sweeper").classes("text-xs text-slate-400")

                def _sweep():
                    res = tb.sweep_orphan_hedges()
                    ui.notify(res.get("message"), type="positive")
                    render_blocks_view()
                    refresh_all_callback()
                ui.button("🧹 SWEEP ORPHAN HEDGES", on_click=_sweep).classes("bg-slate-700 hover:bg-slate-600 text-amber-300 font-bold text-xs px-3 py-1.5 rounded-lg")

        blocks_view_container = ui.column().classes("w-full gap-4")

    def render_blocks_view():
        blocks_view_container.clear()
        blocks = tb.get_all_active_blocks_detailed()
        live_spot = tb.get_live_spot()

        with blocks_view_container:
            if not blocks:
                with ui.card().classes("trade-card w-full p-8 text-center items-center"):
                    ui.icon("check_circle", color="positive", size="3rem")
                    ui.label("CLEAN SLATE: 0 Active Blocks Currently Open").classes("text-sm font-bold text-slate-200 mt-2")
                    ui.label("Deploy an M-Unit, OS-Unit, or Weekly ST Spread to initiate an active block.").classes("text-xs text-slate-400 mt-1")
                return

            for b in blocks:
                bid = b["block_id"]
                bnum = b["block_number"]
                uname = b["unit_name"]
                u_anchor = b["unit_anchor"]
                regime = b["regime"]
                total_pnl = b["total_pnl"]
                status = b["status"]
                pnl_col = "text-emerald-400" if total_pnl >= 0 else "text-red-400"

                with ui.card().classes("trade-card w-full border border-slate-700 mb-2"):
                    # ── Block Header ──
                    with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-3 mb-2"):
                        with ui.column().classes("gap-1"):
                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"BLOCK #{bnum} ({uname})").classes("font-black text-base text-white")
                                ui.badge(status, color="positive" if status == "ACTIVE" else "grey").classes("font-black text-[10px] px-2 py-0.5")
                                ui.badge(f"{'🟢' if regime == 'BULLISH' else '🔴'} {regime}", color="positive" if regime == "BULLISH" else "negative").classes("font-black text-[10px]")

                            ui.label(f"Expiry: {b['expiry_date']} ({b['expiry_type']}) | Master Anchor: ₹{u_anchor:,.2f}").classes("text-xs text-slate-300 font-semibold")

                        with ui.column().classes("items-end gap-0"):
                            ui.label("BLOCK TOTAL P&L").classes("text-[10px] font-bold text-slate-400 tracking-wider")
                            ui.label(f"₹{total_pnl:+,.2f}").classes(f"mono text-xl font-black {pnl_col}")

                    # ── Dedicated Master Anchor Controller ──
                    with ui.expansion(f"🏛️ {uname} Master Anchor Controller (Current: ₹{u_anchor:,.2f})").classes("w-full bg-[#0f141c] text-xs text-slate-200 rounded-lg mb-3"):
                        with ui.row().classes("w-full gap-4 items-center p-2"):
                            anc_input = ui.number(label="Anchor Price (₹)", value=u_anchor, step=25, format="%.2f").classes("w-52 mono")

                            def _save_anc(b_id=bid, inp=anc_input):
                                res = tb.update_block_anchor(b_id, float(inp.value or 0))
                                ui.notify(res.get("message"), type="positive")
                                render_blocks_view()
                                refresh_all_callback()
                            ui.button(f"💾 Save {uname} Anchor", on_click=_save_anc).classes("bg-cyan-600 text-white font-bold text-xs")

                            def _lock_spot(b_id=bid):
                                res = tb.update_block_anchor(b_id, live_spot)
                                ui.notify(res.get("message"), type="positive")
                                render_blocks_view()
                                refresh_all_callback()
                            ui.button(f"⚡ Lock Spot (₹{live_spot:,.1f})", on_click=_lock_spot).classes("bg-slate-700 text-amber-300 font-bold text-xs")

                    # ── CE & PE Split Tables ──
                    with ui.row().classes("w-full gap-4 mb-3"):
                        # CALL Side Table
                        with ui.card().classes("bg-[#0f141c] border border-blue-900/50 flex-1 p-3 rounded-lg"):
                            ui.label("📞 CALL (CE) SPREAD LEGS").classes("font-black text-xs text-blue-400 mb-2")
                            ce_legs = b["ce_strikes"]
                            if not ce_legs:
                                ui.label("No active CE legs in this block.").classes("text-[11px] text-slate-500 italic")
                            else:
                                for s in ce_legs:
                                    sid = s.get("strike_id")
                                    lpnl = s["calculated_pnl"]
                                    lcol = "text-emerald-400" if lpnl >= 0 else "text-red-400"
                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-800 text-xs"):
                                        with ui.column().classes("gap-0"):
                                            ui.label(f"{s.get('strike_price')} CE ({s.get('action')})").classes("font-bold text-white mono")
                                            ui.label(f"Fill: ₹{s.get('fill_price') or s.get('anchor_price', 0):.2f} • LTP: ₹{s.get('current_price') or s.get('ltp', 0):.2f}").classes("text-[10px] text-slate-400 mono")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(f"₹{lpnl:+,.1f}").classes(f"font-black mono text-xs {lcol}")
                                            def _close_leg(s_id=sid):
                                                res = tb.square_off_strike(s_id)
                                                ui.notify(res.get("message"), type="warning")
                                                render_blocks_view()
                                                refresh_all_callback()
                                            ui.button("X", on_click=_close_leg).props("round dense outline size=xs").classes("text-red-400")

                        # PUT Side Table
                        with ui.card().classes("bg-[#0f141c] border border-emerald-900/50 flex-1 p-3 rounded-lg"):
                            ui.label("📉 PUT (PE) SPREAD LEGS").classes("font-black text-xs text-emerald-400 mb-2")
                            pe_legs = b["pe_strikes"]
                            if not pe_legs:
                                ui.label("No active PE legs in this block.").classes("text-[11px] text-slate-500 italic")
                            else:
                                for s in pe_legs:
                                    sid = s.get("strike_id")
                                    lpnl = s["calculated_pnl"]
                                    lcol = "text-emerald-400" if lpnl >= 0 else "text-red-400"
                                    with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-800 text-xs"):
                                        with ui.column().classes("gap-0"):
                                            ui.label(f"{s.get('strike_price')} PE ({s.get('action')})").classes("font-bold text-white mono")
                                            ui.label(f"Fill: ₹{s.get('fill_price') or s.get('anchor_price', 0):.2f} • LTP: ₹{s.get('current_price') or s.get('ltp', 0):.2f}").classes("text-[10px] text-slate-400 mono")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(f"₹{lpnl:+,.1f}").classes(f"font-black mono text-xs {lcol}")
                                            def _close_leg_pe(s_id=sid):
                                                res = tb.square_off_strike(s_id)
                                                ui.notify(res.get("message"), type="warning")
                                                render_blocks_view()
                                                refresh_all_callback()
                                            ui.button("X", on_click=_close_leg_pe).props("round dense outline size=xs").classes("text-red-400")

                    # ── Block Footer Actions ──
                    with ui.row().classes("w-full justify-end items-center gap-3 pt-2"):
                        def _sq_blk(b_id=bid):
                            res = tb.square_off_block(b_id)
                            ui.notify(res.get("message"), type="negative")
                            render_blocks_view()
                            refresh_all_callback()
                        ui.button(f"Square Off Entire Block #{bnum}", on_click=_sq_blk).classes("bg-red-600/80 hover:bg-red-700 text-white font-black text-xs px-3.5 py-1.5 rounded-lg")

    render_blocks_view()
    return render_blocks_view
