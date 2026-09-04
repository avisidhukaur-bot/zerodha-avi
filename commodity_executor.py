"""
commodity_executor.py — Zerodha OptionSelling Engine | MCX Futures Order Engine
=============================================================================
Handles all Zerodha order placement and contract resolution for MCX Futures.
Defines isolated MCX functions to prevent any options engine collisions.
"""

import os
import json
import time
from datetime import datetime, date
from typing import Optional, List, Dict

import db
import config as cfg
import utils
import telegram_bot as tg
from kite_executor import kite_executor


def get_available_contracts(base_symbol: str) -> List[Dict]:
    """
    Returns available future contracts for a commodity symbol, sorted by expiry.
    Uses Zerodha instruments CSV filtered for MCX Futures.
    """
    if not kite_executor.ensure_logged_in():
        return []
        
    try:
        mcx_contracts = kite_executor.get_mcx_futures(base_symbol)
        return mcx_contracts
    except Exception as e:
        print(f"[COMM-EXEC] get_available_contracts exception: {e}")
        return []


def get_mcx_ltp(trading_symbol: str) -> float:
    """Fetches live LTP for a given MCX contract."""
    if not kite_executor.ensure_logged_in():
        return 0.0
    try:
        query = f"MCX:{trading_symbol}"
        res = kite_executor.kite.ltp(query)
        if query in res:
            return float(res[query].get("last_price", 0.0))
    except Exception as e:
        print(f"[COMM-EXEC] Exception in get_mcx_ltp for {trading_symbol}: {e}")
    return 0.0


def get_mcx_tick_size(trading_symbol: str) -> float:
    """Fetches the tick size of the MCX contract from the cached instruments list."""
    try:
        df = kite_executor._load_security_master()
        if not df.empty:
            filtered = df[df["tradingsymbol"].str.upper() == trading_symbol.upper()]
            if not filtered.empty:
                return float(filtered.iloc[0].get("tick_size", 0.05))
    except Exception as e:
        print(f"[COMM-EXEC] Failed to get tick size for {trading_symbol}: {e}")
    return 0.05  # Default fallback


def place_mcx_order(trading_symbol: str, transaction_type: str, qty: int) -> bool:
    """Places a protected LIMIT order (acting as a market order) for an MCX future contract via Zerodha."""
    if not kite_executor.ensure_logged_in():
        print("[COMM-EXEC] MCX ORDER FAILED: Zerodha not logged in.")
        return False
        
    try:
        tx_type = (
            kite_executor.kite.TRANSACTION_TYPE_BUY 
            if transaction_type.upper() == "BUY" 
            else kite_executor.kite.TRANSACTION_TYPE_SELL
        )
        
        # Query LTP to convert to a protected LIMIT order
        ltp = get_mcx_ltp(trading_symbol)
        if ltp <= 0:
            print(f"[COMM-EXEC] Failed to get live LTP for order protection: {trading_symbol}")
            return False
            
        # Add 1.0% buffer for Buy, subtract 1.0% for Sell
        if transaction_type.upper() == "BUY":
            limit_price = ltp * 1.01  # +1% protection
        else:
            limit_price = ltp * 0.99  # -1% protection
            
        # Get dynamic tick size from security master and round to nearest tick size
        tick_size = get_mcx_tick_size(trading_symbol)
        limit_price = round(limit_price / tick_size) * tick_size
        
        print(f"[COMM-EXEC] Converting MCX Market order to Limit with protection: LTP={ltp} -> Limit={limit_price} (Tick={tick_size})")
        
        order_id = kite_executor.kite.place_order(
            variety=kite_executor.kite.VARIETY_REGULAR,
            exchange=kite_executor.kite.EXCHANGE_MCX,  # "MCX"
            tradingsymbol=trading_symbol.upper(),
            transaction_type=tx_type,
            quantity=int(qty),
            product=kite_executor.kite.PRODUCT_MIS,  # Intraday
            order_type=kite_executor.kite.ORDER_TYPE_LIMIT,
            price=float(limit_price)
        )
        
        if order_id:
            print(f"[COMM-EXEC] MCX ORDER PLACED ({transaction_type}): {trading_symbol} × {qty} | LimitPrice={limit_price} | OrderID={order_id}")
            # Poll order fill
            filled = kite_executor.poll_order_fill(order_id, max_attempts=6, delay_sec=2.0)
            if filled:
                avg_price = kite_executor.get_order_fill_price(order_id)
                if avg_price > 0:
                    db.set("comm_entry_price", str(avg_price))
                print(f"[COMM-EXEC] MCX ORDER FILLED successfully: {trading_symbol} | ExecutedPrice={avg_price or limit_price}")
                return True
            else:
                print(f"[COMM-EXEC] MCX ORDER FAILED to fill: {order_id}")
                return False
        else:
            print(f"[COMM-EXEC] MCX ORDER FAILED ({transaction_type}): No OrderID returned.")
            return False
    except Exception as e:
        print(f"[COMM-EXEC] place_mcx_order exception: {e}")
        tg.send_silent(f"❌ <b>MCX {transaction_type} ORDER FAILED</b>\nSymbol: {trading_symbol}\nError: {e}")
        return False


def get_all_mcx_positions() -> List[Dict]:
    """
    Retrieves all active MCX positions from the exchange via Zerodha.
    """
    if not kite_executor.ensure_logged_in():
        return []
    try:
        positions = kite_executor.get_positions()
        mcx_pos = [
            p for p in positions
            if abs(float(p.get("quantity", 0))) > 0
            and p.get("exchange", "").upper() == "MCX"
        ]
        return mcx_pos
    except Exception as e:
        print(f"[COMM-EXEC] get_all_mcx_positions exception: {e}")
        return []


def execute_commodity_flip(target_dir: str) -> bool:
    """
    Executes a flip order on the exchange.
    target_dir can be "LONG" or "SHORT".
    
    If holding opposite direction, places a double-lot order to reverse net position.
    """
    contract_key = db.get("comm_selected_contract", "")
    if not contract_key:
        print("[COMM-EXEC] Flip triggered but no commodity contract selected.")
        return False
        
    lots = int(db.get("comm_lots", "1") or 1)
    lot_size = int(db.get("comm_lot_size", "1") or 1)
    target_qty = lots * lot_size
    
    # 1. Fetch live positions from exchange
    positions = get_all_mcx_positions()
    active_pos = None
    for p in positions:
        if p.get("tradingsymbol", "").upper() == contract_key.upper():
            active_pos = p
            break
            
    current_qty = int(float(active_pos.get("quantity", 0))) if active_pos else 0
    current_dir = "LONG" if current_qty > 0 else "SHORT" if current_qty < 0 else "FLAT"
    
    if current_dir == target_dir:
        print(f"[COMM-EXEC] Already in target position {target_dir} ({current_qty} units). No trade required.")
        db.set("comm_position_state", target_dir)
        return True
        
    print(f"[COMM-EXEC] Flip Triggered: {current_dir} ({current_qty} units) ──► {target_dir} ({target_qty} units)")
    
    # Determine transaction type and flip quantity
    if target_dir == "LONG":
        tx_type = "BUY"
        if current_dir == "SHORT":
            # Reversal: Buy 2x the target quantity (squares off short and enters long)
            order_qty = abs(current_qty) + target_qty
        else:
            # Fresh Entry: Buy target quantity
            order_qty = target_qty
    else:  # SHORT
        tx_type = "SELL"
        if current_dir == "LONG":
            # Reversal: Sell 2x the target quantity (squares off long and enters short)
            order_qty = abs(current_qty) + target_qty
        else:
            # Fresh Entry: Sell target quantity
            order_qty = target_qty
            
    # 2. Place the order
    success = place_mcx_order(contract_key, tx_type, order_qty)
    if success:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.set("comm_position_state", target_dir)
        db.set("comm_entry_time", now_str)
        
        # Read the price set by the executor (or fallback to LTP)
        exec_price = float(db.get("comm_entry_price", "0.0") or 0.0)
        if exec_price <= 0:
            exec_price = get_mcx_ltp(contract_key)
            db.set("comm_entry_price", str(exec_price))
            
        # Notify via Telegram
        tg.send_silent(
            f"🔄 <b>COMMODITY POSITION FLIP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Contract:</b> {contract_key}\n"
            f"<b>Direction:</b> {current_dir} ──► {target_dir}\n"
            f"<b>Executed Qty:</b> {order_qty} units ({order_qty//lot_size} lots)\n"
            f"<b>Execution Price:</b> ₹{exec_price:.2f}\n"
            f"<b>Status:</b> Position Synced & Active"
        )
        return True
        
    return False


def square_off_all_mcx_positions() -> bool:
    """
    Squares off all open MCX positions on the exchange.
    Resets commodity trading state in the database.
    """
    print("[COMM-EXEC] COMMODITY SQUARE OFF: Squaring off all MCX positions...")
    positions = get_all_mcx_positions()
    
    if not positions:
        print("[COMM-EXEC] No open MCX positions found to square off.")
        _clear_comm_db_state()
        return True
        
    all_success = True
    for p in positions:
        sym = p.get("tradingsymbol", "")
        qty = int(float(p.get("quantity", 0)))
        
        if qty > 0:
            # Square off Long by Selling
            success = place_mcx_order(sym, "SELL", qty)
        else:
            # Square off Short by Buying
            success = place_mcx_order(sym, "BUY", abs(qty))
            
        if not success:
            all_success = False
            
    if all_success:
        _clear_comm_db_state()
        tg.send_silent(
            f"🛑 <b>COMMODITY SQUARE OFF COMPLETE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"All MCX open positions have been squared off.\n"
            f"Commodity Engine state reset to FLAT."
        )
        
    return all_success


def _clear_comm_db_state():
    """Resets the commodity position database keys."""
    db.set("comm_position_state", "FLAT")
    db.set("comm_entry_price", "0.0")
    db.set("comm_entry_time", "")
    db.set("comm_unrealized_pnl_pct", "0.0")
