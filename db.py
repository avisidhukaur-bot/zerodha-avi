"""
db.py -- Zerodha OptionSelling Engine | Brick 1
==============================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 1)
Date     : June 2026

DATABASE SCHEMA (5 Tables per Blueprint):
  1. blocks   -- Trading containers (one per expiry)
  2. strikes  -- CE/PE sell + hedge legs per block
  3. legs     -- Live position tracking (fills)
  4. trades   -- Full history log of all actions
  5. settings -- App config + secrets (in-memory only for secrets)

HARD RULES (from Blueprint):
  - NIFTY only. Max strikes per block configured in settings.
  - One expiry per block.
  - Anchor price = manual (never auto-set).
  - Cannot delete block if any strike is OPEN.
"""

import sqlite3
import os
import sys
import threading
from typing import Optional, List, Dict, Any, Union

# Force UTF-8 output on Windows (prevents emoji/unicode crash on cp1252 terminals)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
import pytz

import config as cfg

# ─────────────────────────────────────────────────────────────────────────────
# Timezone Helper
# ─────────────────────────────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")


def _ist_now() -> str:
    """Returns current IST datetime as string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# Connection Pool (thread-safe)
# ─────────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    """
    Opens a SQLite connection and ensures all 5 tables exist.
    Called internally -- always close connection after use.
    """
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Allows dict-style access: row["column"]
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read/write
    conn.execute("PRAGMA foreign_keys=ON")   # Enforce FK constraints

    # ── Table 1: blocks ──────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            block_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            block_number        INTEGER NOT NULL,
            expiry_date         TEXT    NOT NULL,
            expiry_type         TEXT    NOT NULL DEFAULT 'MONTHLY',
            side_type           TEXT    NOT NULL DEFAULT 'BOTH',
            anchor_unit_name    TEXT    NOT NULL DEFAULT 'M1',
            master_anchor_price REAL    NOT NULL DEFAULT 0.0,
            regime_buffer       REAL    NOT NULL DEFAULT 15.0,
            current_regime      TEXT    NOT NULL DEFAULT 'NEUTRAL',
            auto_regime_enabled INTEGER NOT NULL DEFAULT 1,
            custom_lots         INTEGER NOT NULL DEFAULT 2,
            is_enabled          INTEGER NOT NULL DEFAULT 1,
            status              TEXT    NOT NULL DEFAULT 'ACTIVE',
            created_at          TEXT    NOT NULL,
            notes               TEXT    DEFAULT ''
        )
    """)

    # ── Table 2: strikes ─────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strikes (
            strike_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            block_id        INTEGER NOT NULL REFERENCES blocks(block_id),
            strike_price    INTEGER NOT NULL,
            option_type     TEXT    NOT NULL,
            leg_type        TEXT    NOT NULL,
            anchor_price    REAL    NOT NULL DEFAULT 0.0,
            lots            INTEGER NOT NULL DEFAULT 1,
            status          TEXT    NOT NULL DEFAULT 'PENDING',
            hedge_strike_id INTEGER DEFAULT NULL
        )
    """)

    # ── Table 3: legs (live position tracking) ───────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS legs (
            leg_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            strike_id     INTEGER NOT NULL REFERENCES strikes(strike_id),
            entry_price   REAL    DEFAULT 0.0,
            exit_price    REAL    DEFAULT 0.0,
            entry_time    TEXT    DEFAULT '',
            exit_time     TEXT    DEFAULT '',
            realized_pnl  REAL    DEFAULT 0.0,
            order_id      TEXT    DEFAULT ''
        )
    """)

    # ── Table 4: trades (history log) ────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            block_id     INTEGER NOT NULL,
            strike_id    INTEGER NOT NULL,
            action       TEXT    NOT NULL,
            price        REAL    NOT NULL DEFAULT 0.0,
            lots         INTEGER NOT NULL DEFAULT 0,
            timestamp    TEXT    NOT NULL,
            order_status TEXT    NOT NULL DEFAULT ''
        )
    """)

    # ── Table 5: settings (app config) ───────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Column migrations for backward compatibility
    try:
        conn.execute("ALTER TABLE strikes ADD COLUMN expiry_date TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN side_type TEXT DEFAULT 'BOTH'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN is_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN anchor_unit_name TEXT DEFAULT 'M1'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN master_anchor_price REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN regime_buffer REAL DEFAULT 15.0")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN current_regime TEXT DEFAULT 'NEUTRAL'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN auto_regime_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN custom_lots INTEGER DEFAULT 2")
    except sqlite3.OperationalError:
        pass

    # ── V5.0 'Old & Gold' Architecture Migrations ───────────────────────────
    # Strikes Table Migrations
    try:
        conn.execute("ALTER TABLE strikes ADD COLUMN sl_pct REAL DEFAULT 25.0")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE strikes ADD COLUMN sl_price REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE strikes ADD COLUMN reentry_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE strikes ADD COLUMN trade_state TEXT DEFAULT 'OPEN'")
    except sqlite3.OperationalError:
        pass

    # Blocks Table Migrations
    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN anchor_decision_time TEXT DEFAULT '15:00'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN recommended_lots INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE blocks ADD COLUMN orphan_hedge_policy TEXT DEFAULT 'PRESERVE'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Secrets Store (credentials NEVER go to SQLite)
# ─────────────────────────────────────────────────────────────────────────────
_SECRETS: dict = {}
_secrets_loaded: bool = False

SECRET_KEYS = {
    "KITE_API_KEY",
    "KITE_API_SECRET",
    "KITE_CLIENT_CODE",
    "KITE_PASSWORD",
    "KITE_TOTP_KEY",
    "NTFY_TOPIC",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "ALLOWED_TRADING_IP",
    "VPS_IP",
    "VPS_USER",
    "VPS_PASSWORD",
}


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS -- Key-Value Store
# ─────────────────────────────────────────────────────────────────────────────

def get(key: str, default: str = "") -> str:
    """
    Get a setting value.
    - Secret keys -> returned from in-memory store only (never SQLite)
    - Other keys  -> returned from SQLite settings table
    """
    key_upper = key.upper()
    if key_upper in SECRET_KEYS:
        return _SECRETS.get(key_upper, default)
    try:
        conn = _conn()
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default


def set(key: str, value) -> None:
    """
    Set a setting value.
    - Secret keys -> stored in in-memory store only
    - Other keys  -> stored in SQLite settings table
    """
    key_upper = key.upper()
    if key_upper in SECRET_KEYS:
        _SECRETS[key_upper] = str(value)
        return
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[DB] set() error for key '{key}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECRETS -- Load from secrets.txt
# ─────────────────────────────────────────────────────────────────────────────

def load_secrets() -> bool:
    """
    Loads credentials from secrets.txt into in-memory store only.
    Secrets are NEVER written to SQLite.
    """
    global _secrets_loaded
    if not os.path.exists(cfg.SECRETS_PATH):
        if not _secrets_loaded:
            print(f"[DB] WARN  secrets.txt not found at: {cfg.SECRETS_PATH}")
            _secrets_loaded = True
        return False

    loaded = []
    try:
        with open(cfg.SECRETS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip().upper()
                v = v.strip()
                if k and v:
                    set(k, v)
                    loaded.append(k)
        if loaded:
            if not _secrets_loaded:
                print(f"[DB] OK Loaded {len(loaded)} secrets from secrets.txt")
                _secrets_loaded = True
            return True
    except Exception as e:
        print(f"[DB] ERR Error reading secrets.txt: {e}")
    return False


def save_secrets_to_file(secrets_dict: dict) -> bool:
    """
    Updates secrets.txt with new values for specified keys.
    Preserves comments and other keys.
    """
    import os
    try:
        # Load existing lines
        lines = []
        if os.path.exists(cfg.SECRETS_PATH):
            with open(cfg.SECRETS_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # Parse and update
        updated_keys = {}
        new_lines = []
        for line in lines:
            stripped = line.strip()
            # If line is an assignment, check if it's a target key
            if stripped and not stripped.startswith("#") and "=" in line:
                k, sep, v = line.partition("=")
                k_clean = k.strip().upper()
                if k_clean in secrets_dict:
                    new_lines.append(f"{k.strip()}={secrets_dict[k_clean]}\n")
                    updated_keys[k_clean] = True
                    continue
            new_lines.append(line)
        
        # Add any new keys that weren't in the file
        for k, v in secrets_dict.items():
            k_upper = k.upper()
            if k_upper not in updated_keys:
                new_lines.append(f"{k_upper}={v}\n")
        
        # Write back
        with open(cfg.SECRETS_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        # Also update in-memory cache
        for k, v in secrets_dict.items():
            set(k, v)
        return True
    except Exception as e:
        print(f"[DB] Error saving secrets to file: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MASTER NIFTY REGIME SETTINGS HELPERS (Brick 1)
# ─────────────────────────────────────────────────────────────────────────────

def get_master_nifty_anchor() -> float:
    """Returns the Master Nifty Anchor price as float (0.0 if not set)."""
    try:
        val = get("master_nifty_anchor", str(getattr(cfg, "DEFAULT_MASTER_NIFTY_ANCHOR", 0.0)))
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def set_master_nifty_anchor(price: float) -> None:
    """Sets the Master Nifty Anchor price in settings."""
    set("master_nifty_anchor", f"{float(price):.2f}")


def get_regime_buffer() -> float:
    """Returns the hysteresis buffer in points for whipsaw protection (default 15.0 pts)."""
    try:
        val = get("regime_buffer", str(getattr(cfg, "DEFAULT_REGIME_BUFFER", 15.0)))
        return float(val)
    except (ValueError, TypeError):
        return 15.0


def set_regime_buffer(buffer_pts: float) -> None:
    """Sets the hysteresis buffer in points."""
    set("regime_buffer", f"{float(buffer_pts):.2f}")


def get_regime_mode() -> str:
    """Returns regime mode: 'AUTO', 'MANUAL', or 'OFF'."""
    val = get("regime_mode", getattr(cfg, "DEFAULT_REGIME_MODE", "AUTO")).strip().upper()
    return val if val in ("AUTO", "MANUAL", "OFF") else "AUTO"


def set_regime_mode(mode: str) -> None:
    """Sets regime mode."""
    mode_clean = str(mode).strip().upper()
    if mode_clean not in ("AUTO", "MANUAL", "OFF"):
        mode_clean = "AUTO"
    set("regime_mode", mode_clean)


def get_active_regime() -> str:
    """Returns current active regime: 'BULLISH', 'BEARISH', or 'NEUTRAL'."""
    return get("active_regime", "NEUTRAL").strip().upper()


def set_active_regime(regime: str) -> None:
    """Sets current active regime."""
    set("active_regime", str(regime).strip().upper())




# ─────────────────────────────────────────────────────────────────────────────
# ██████  BLOCKS CRUD
# ─────────────────────────────────────────────────────────────────────────────

def get_next_unit_name(expiry_date: str = None) -> str:
    """
    Finds the next unit identifier (e.g. M1, M2, M3...) for active blocks.
    """
    try:
        conn = _conn()
        if expiry_date:
            cur = conn.execute("SELECT anchor_unit_name FROM blocks WHERE status='ACTIVE' AND UPPER(expiry_date)=UPPER(?)", (expiry_date.strip(),))
        else:
            cur = conn.execute("SELECT anchor_unit_name FROM blocks WHERE status='ACTIVE'")
        existing_units = [row["anchor_unit_name"].strip().upper() for row in cur.fetchall() if row["anchor_unit_name"]]
        conn.close()

        # Find first free M_i
        for i in range(1, 100):
            candidate = f"M{i}"
            if candidate not in existing_units:
                return candidate
        return f"M{len(existing_units) + 1}"
    except Exception:
        return "M1"


def create_block(
    expiry_date: str,
    expiry_type: str = "MONTHLY",
    side_type: str = "BOTH",
    notes: str = "",
    anchor_unit_name: str = "",
    master_anchor_price: float = 0.0,
    regime_buffer: float = 15.0,
    custom_lots: int = 2,
    current_regime: str = "NEUTRAL",
    auto_regime_enabled: int = 1,
    anchor_decision_time: str = "15:00",
    recommended_lots: int = 1,
    orphan_hedge_policy: str = "PRESERVE"
) -> int:
    """
    Creates a new block. Auto-assigns next block_number and unit name if not supplied.
    expiry_date         : "26-Jun-2025"
    expiry_type         : "MONTHLY" / "WEEKLY"
    side_type           : "CALL" / "PUT" / "BOTH"
    anchor_unit_name    : "M1", "M2", etc.
    master_anchor_price : Dedicated unit anchor (0.0 = unset)
    regime_buffer       : Hysteresis buffer (default 15.0 pts)
    anchor_decision_time: "15:00" (3:00 PM Continuation Decision)
    Returns             : block_id (int) or -1 on failure
    """
    side_type_clean = side_type.strip().upper()
    if side_type_clean not in ("CALL", "PUT", "BOTH"):
        side_type_clean = "BOTH"

    unit_name = str(anchor_unit_name).strip().upper() if anchor_unit_name else "M1"


    try:
        with _lock:
            conn = _conn()
            # Auto-assign next block number
            cur = conn.execute("SELECT COALESCE(MAX(block_number), 0) FROM blocks")
            next_num = cur.fetchone()[0] + 1

            conn.execute(
                """
                INSERT INTO blocks (
                    block_number, expiry_date, expiry_type, side_type,
                    anchor_unit_name, master_anchor_price, regime_buffer,
                    current_regime, auto_regime_enabled, custom_lots,
                    anchor_decision_time, recommended_lots, orphan_hedge_policy,
                    is_enabled, status, created_at, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'ACTIVE', ?, ?)
                """,
                (
                    next_num, expiry_date, expiry_type.upper(), side_type_clean,
                    unit_name, float(master_anchor_price), float(regime_buffer),
                    str(current_regime).upper(), int(auto_regime_enabled), int(custom_lots),
                    str(anchor_decision_time), int(recommended_lots), str(orphan_hedge_policy),
                    _ist_now(), notes
                )
            )
            conn.commit()
            block_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            print(f"[DB] OK Block {next_num} [{unit_name}] created -> block_id={block_id} | Anchor: {master_anchor_price} | Expiry: {expiry_date} ({expiry_type}) | Side: {side_type_clean}")
            return block_id
    except Exception as e:
        print(f"[DB] ERR create_block() failed: {e}")
        return -1
        return -1


def update_block_anchor(
    block_id: int,
    master_anchor_price: float,
    regime_buffer: float = 15.0,
    anchor_unit_name: str = None
) -> bool:
    """Updates master anchor, buffer, and optionally unit name for a specific block."""
    try:
        with _lock:
            conn = _conn()
            if anchor_unit_name:
                conn.execute(
                    "UPDATE blocks SET master_anchor_price=?, regime_buffer=?, anchor_unit_name=? WHERE block_id=?",
                    (float(master_anchor_price), float(regime_buffer), str(anchor_unit_name).strip().upper(), block_id)
                )
            else:
                conn.execute(
                    "UPDATE blocks SET master_anchor_price=?, regime_buffer=? WHERE block_id=?",
                    (float(master_anchor_price), float(regime_buffer), block_id)
                )
            conn.commit()
            conn.close()
        print(f"[DB] OK Block {block_id} anchor updated -> ₹{master_anchor_price:.2f} (Buffer: ±{regime_buffer:.1f})")
        return True
    except Exception as e:
        print(f"[DB] ERR update_block_anchor() failed: {e}")
        return False


def update_block_regime(block_id: int, current_regime: str) -> bool:
    """Updates active regime ('BULLISH', 'BEARISH', 'NEUTRAL') for a specific block."""
    reg = str(current_regime).strip().upper()
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE blocks SET current_regime=? WHERE block_id=?",
                (reg, block_id)
            )
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_block_regime() failed: {e}")
        return False


def toggle_block_enabled(block_id: int, is_enabled: bool) -> bool:
    """
    Toggles is_enabled status (1 for ENABLED, 0 for PAUSED) for a block.
    """
    val = 1 if is_enabled else 0
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE blocks SET is_enabled=? WHERE block_id=?",
                (val, block_id)
            )
            conn.commit()
            conn.close()
        status_str = "ENABLED" if val == 1 else "PAUSED"
        print(f"[DB] OK Block {block_id} set to {status_str}")
        return True
    except Exception as e:
        print(f"[DB] ERR toggle_block_enabled() failed: {e}")
        return False


def get_block(block_id: int) -> dict:
    """Returns a single block as dict, or {} if not found."""
    try:
        conn = _conn()
        cur = conn.execute("SELECT * FROM blocks WHERE block_id=?", (block_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        print(f"[DB] ERR get_block() failed: {e}")
        return {}


def get_all_blocks(status_filter: str = None) -> list:
    """
    Returns all blocks as list of dicts.
    status_filter: "ACTIVE" / "EXPIRED" / "CLOSED" -- or None for all
    """
    try:
        conn = _conn()
        if status_filter:
            cur = conn.execute(
                "SELECT * FROM blocks WHERE status=? ORDER BY block_number ASC",
                (status_filter.upper(),)
            )
        else:
            cur = conn.execute("SELECT * FROM blocks ORDER BY block_number ASC")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] ERR get_all_blocks() failed: {e}")
        return []


def update_block_status(block_id: int, status: str) -> bool:
    """
    Updates block status: 'ACTIVE' / 'EXPIRED' / 'CLOSED'
    HARD RULE: Cannot close/delete block if any strike is OPEN.
    """
    if status.upper() in ("CLOSED", "DELETED"):
        open_strikes = get_strikes_by_block(block_id, status_filter="OPEN")
        if open_strikes:
            print(f"[DB] BLOCKED HARD RULE: Cannot close Block {block_id} -- {len(open_strikes)} strike(s) still OPEN.")
            return False
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE blocks SET status=? WHERE block_id=?",
                (status.upper(), block_id)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Block {block_id} status -> {status.upper()}")
        return True
    except Exception as e:
        print(f"[DB] ERR update_block_status() failed: {e}")
        return False


def update_block_expiry(block_id: int, expiry_date: str, expiry_type: str) -> bool:
    """
    Updates expiry_date and expiry_type for a block.
    Used by dashboard Block Edit feature.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE blocks SET expiry_date=?, expiry_type=? WHERE block_id=?",
                (expiry_date, expiry_type.upper(), block_id)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Block {block_id} expiry updated -> {expiry_date} ({expiry_type.upper()})")
        return True
    except Exception as e:
        print(f"[DB] ERR update_block_expiry() failed: {e}")
        return False


def delete_block(block_id: int) -> bool:
    """
    HARD RULE: Cannot delete if any strike is OPEN.
    Deletes block + all its strikes + legs + trades.
    """
    open_strikes = get_strikes_by_block(block_id, status_filter="OPEN")
    if open_strikes:
        print(f"[DB] BLOCKED HARD RULE: Cannot delete Block {block_id} -- {len(open_strikes)} strike(s) still OPEN.")
        return False
    try:
        with _lock:
            conn = _conn()
            # Cascade delete: legs -> strikes -> trades -> block
            strike_ids = [r["strike_id"] for r in get_strikes_by_block(block_id)]
            for sid in strike_ids:
                conn.execute("DELETE FROM legs WHERE strike_id=?", (sid,))
            conn.execute("DELETE FROM strikes WHERE block_id=?", (block_id,))
            conn.execute("DELETE FROM trades WHERE block_id=?", (block_id,))
            conn.execute("DELETE FROM blocks WHERE block_id=?", (block_id,))
            conn.commit()
            conn.close()
        print(f"[DB] OK Block {block_id} fully deleted (cascade).")
        return True
    except Exception as e:
        print(f"[DB] ERR delete_block() failed: {e}")
        return False


def force_delete_block(block_id: int) -> bool:
    """
    Force deletes a block and all its strikes, legs, trades, and pending settings,
    bypassing the hard rule check for open strikes.
    """
    try:
        with _lock:
            conn = _conn()
            # Cascade delete: legs -> settings (pending_close_time) -> strikes -> trades -> block
            strike_ids = [r["strike_id"] for r in get_strikes_by_block(block_id)]
            for sid in strike_ids:
                conn.execute("DELETE FROM legs WHERE strike_id=?", (sid,))
                conn.execute("DELETE FROM settings WHERE key=?", (f"pending_close_time_{sid}",))
            conn.execute("DELETE FROM strikes WHERE block_id=?", (block_id,))
            conn.execute("DELETE FROM trades WHERE block_id=?", (block_id,))
            conn.execute("DELETE FROM blocks WHERE block_id=?", (block_id,))
            conn.commit()
            conn.close()
        print(f"[DB] OK Block {block_id} force deleted (cascade).")
        return True
    except Exception as e:
        print(f"[DB] ERR force_delete_block() failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ██████  STRIKES CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_strike(
    block_id: int,
    strike_price: int,
    option_type: str,
    leg_type: str,
    anchor_price: float,
    lots: int = 1,
    hedge_strike_id: int = None,
    expiry_date: str = None,
    sl_pct: float = 25.0,
    sl_price: float = 0.0,
    reentry_enabled: int = 1,
    trade_state: str = "PENDING"
) -> int:
    """
    Adds a strike (leg) to a block.
    HARD RULE: Max strikes per block configured in settings.
    HARD RULE: option_type must be CE/PE.
    HARD RULE: leg_type must be SELL or HEDGE_BUY.
    HARD RULE: Anchor price must be manually provided (> 0).
    Returns: strike_id or -1 on failure.
    """
    # ── Validate option_type ──────────────────────────────────────────────────
    option_type = option_type.upper()
    if option_type not in ("CE", "PE"):
        print(f"[DB] BLOCKED HARD RULE: option_type must be CE or PE. Got: {option_type}")
        return -1

    # ── Validate leg_type ─────────────────────────────────────────────────────
    leg_type = leg_type.upper()
    if leg_type not in ("SELL", "HEDGE_BUY"):
        print(f"[DB] BLOCKED HARD RULE: leg_type must be SELL or HEDGE_BUY. Got: {leg_type}")
        return -1

    # ── Validate anchor_price ─────────────────────────────────────────────────
    if leg_type == "SELL" and anchor_price <= 0:
        print(f"[DB] BLOCKED HARD RULE: Anchor price must be > 0 (manual entry required) for SELL strikes. Got: {anchor_price}")
        return -1
    elif leg_type == "HEDGE_BUY" and anchor_price < 0:
        print(f"[DB] BLOCKED HARD RULE: Anchor price must be >= 0 for HEDGE_BUY strikes. Got: {anchor_price}")
        return -1

    # ── Enforce max strikes per block ──────────────────────────────────────
    max_strikes = int(get("max_strikes_per_block", "50"))
    existing = get_strikes_by_block(block_id)
    if len(existing) >= max_strikes:
        print(f"[DB] BLOCKED HARD RULE: Block {block_id} already has {len(existing)} strikes (MAX = {max_strikes}).")
        return -1

    # ── Verify block exists ───────────────────────────────────────────────────
    block = get_block(block_id)
    if not block:
        print(f"[DB] ERR Block {block_id} not found.")
        return -1

    # ── Auto-compute sl_price if not explicitly provided ─────────────────────
    if leg_type == "SELL" and sl_price <= 0 and anchor_price > 0:
        sl_price = anchor_price * (1.0 + (float(sl_pct) / 100.0))

    try:
        with _lock:
            conn = _conn()
            conn.execute(
                """
                INSERT INTO strikes
                    (block_id, strike_price, option_type, leg_type, anchor_price, lots, status,
                     hedge_strike_id, expiry_date, sl_pct, sl_price, reentry_enabled, trade_state)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?)
                """,
                (block_id, strike_price, option_type, leg_type,
                 anchor_price, lots, hedge_strike_id, expiry_date,
                 float(sl_pct), float(sl_price), int(reentry_enabled), str(trade_state).upper())
            )
            conn.commit()
            strike_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
        print(
            f"[DB] OK Strike added -> strike_id={strike_id} | "
            f"Block {block_id} | {strike_price} {option_type} {leg_type} | "
            f"Anchor=₹{anchor_price:.2f} | Lots={lots} | Expiry={expiry_date} | SL={sl_pct}% (Trigger=₹{sl_price:.2f})"
        )
        return strike_id
    except Exception as e:
        print(f"[DB] ERR add_strike() failed: {e}")
        return -1


def get_strike(strike_id: int) -> dict:
    """Returns a single strike as dict, or {} if not found."""
    try:
        conn = _conn()
        cur = conn.execute("SELECT * FROM strikes WHERE strike_id=?", (strike_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        print(f"[DB] ERR get_strike() failed: {e}")
        return {}


def get_strikes_by_block(block_id: int, status_filter: str = None) -> list:
    """
    Returns all strikes for a block as list of dicts.
    status_filter: 'OPEN' / 'CLOSED' / 'PENDING' -- or None for all
    """
    try:
        conn = _conn()
        if status_filter:
            if status_filter.upper() == "OPEN":
                cur = conn.execute(
                    "SELECT * FROM strikes WHERE block_id=? AND status IN ('OPEN', 'PENDING_CLOSE') ORDER BY strike_id ASC",
                    (block_id,)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM strikes WHERE block_id=? AND status=? ORDER BY strike_id ASC",
                    (block_id, status_filter.upper())
                )
        else:
            cur = conn.execute(
                "SELECT * FROM strikes WHERE block_id=? ORDER BY strike_id ASC",
                (block_id,)
            )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] ERR get_strikes_by_block() failed: {e}")
        return []


def update_strike_status(strike_id: int, status: str) -> bool:
    """Updates strike status: 'PENDING' / 'OPEN' / 'CLOSED'"""
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE strikes SET status=? WHERE strike_id=?",
                (status.upper(), strike_id)
            )
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_status() failed: {e}")
        return False


def update_strike_trade_state(strike_id: int, trade_state: str) -> bool:
    """Updates the granular trade state ('OPEN', 'PENDING', 'SL_HIT', 'REENTRY_ELIGIBLE', 'CONTINUED', 'CLOSED', 'ORPHAN')."""
    try:
        with _lock:
            conn = _conn()
            conn.execute("UPDATE strikes SET trade_state=? WHERE strike_id=?", (trade_state.upper(), strike_id))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_trade_state() failed: {e}")
        return False


def update_strike_sl_config(strike_id: int, sl_pct: float, sl_price: float = 0.0) -> bool:
    """Updates stop-loss percentage and absolute SL price for a strike."""
    try:
        with _lock:
            conn = _conn()
            conn.execute("UPDATE strikes SET sl_pct=?, sl_price=? WHERE strike_id=?", (float(sl_pct), float(sl_price), strike_id))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_sl_config() failed: {e}")
        return False


def update_strike_pricing_and_sl(
    strike_id: int,
    anchor_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    sl_pct: Optional[float] = None,
    lots: Optional[int] = None
) -> bool:
    """Updates strike's anchor price, stop loss price, stop loss percentage, and lots in one atomic query."""
    try:
        fields = []
        params = []
        if anchor_price is not None and anchor_price > 0:
            fields.append("anchor_price=?")
            params.append(float(anchor_price))
        if sl_price is not None and sl_price >= 0:
            fields.append("sl_price=?")
            params.append(float(sl_price))
        if sl_pct is not None and sl_pct > 0:
            fields.append("sl_pct=?")
            params.append(float(sl_pct))
        if lots is not None and lots >= 1:
            fields.append("lots=?")
            params.append(int(lots))
        
        if not fields:
            return True
        
        params.append(strike_id)
        sql = f"UPDATE strikes SET {', '.join(fields)} WHERE strike_id=?"
        with _lock:
            conn = _conn()
            conn.execute(sql, tuple(params))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_pricing_and_sl() failed: {e}")
        return False


def update_strike_reentry(strike_id: int, reentry_enabled: int) -> bool:
    """Enables or disables auto re-entry for a strike."""
    try:
        with _lock:
            conn = _conn()
            conn.execute("UPDATE strikes SET reentry_enabled=? WHERE strike_id=?", (int(reentry_enabled), strike_id))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_reentry() failed: {e}")
        return False


def get_orphan_hedges(block_id: int = None) -> list:
    """Returns list of open long hedge strikes where the associated short leg has exited/closed."""
    try:
        conn = _conn()
        if block_id:
            cur = conn.execute("""
                SELECT h.* FROM strikes h
                WHERE h.leg_type = 'HEDGE_BUY' AND h.status = 'OPEN' AND h.block_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM strikes s 
                    WHERE s.hedge_strike_id = h.strike_id AND s.status = 'OPEN' AND s.leg_type = 'SELL'
                )
            """, (block_id,))
        else:
            cur = conn.execute("""
                SELECT h.* FROM strikes h
                WHERE h.leg_type = 'HEDGE_BUY' AND h.status = 'OPEN'
                AND NOT EXISTS (
                    SELECT 1 FROM strikes s 
                    WHERE s.hedge_strike_id = h.strike_id AND s.status = 'OPEN' AND s.leg_type = 'SELL'
                )
            """)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] ERR get_orphan_hedges() failed: {e}")
        return []


def try_set_strike_executing(strike_id: int) -> bool:
    """
    Atomically tries to set strike status to 'EXECUTING' if it is 'PENDING'.
    Returns True if successful (exactly 1 row updated), False otherwise.
    """
    try:
        with _lock:
            conn = _conn()
            cur = conn.execute(
                "UPDATE strikes SET status='EXECUTING' WHERE strike_id=? AND status='PENDING'",
                (strike_id,)
            )
            conn.commit()
            updated = cur.rowcount > 0
            conn.close()
        return updated
    except Exception as e:
        print(f"[DB] ERR try_set_strike_executing() failed: {e}")
        return False


def try_set_strike_reentering(strike_id: int) -> bool:
    """
    Atomically transitions strike status from 'CLOSED' to 'EXECUTING'.
    Returns True if successful (exactly 1 row updated), False otherwise.
    """
    try:
        with _lock:
            conn = _conn()
            cur = conn.execute(
                "UPDATE strikes SET status='EXECUTING' WHERE strike_id=? AND status='CLOSED'",
                (strike_id,)
            )
            conn.commit()
            updated = cur.rowcount > 0
            conn.close()
        return updated
    except Exception as e:
        print(f"[DB] ERR try_set_strike_reentering() failed: {e}")
        return False



def update_strike_anchor_price(strike_id: int, anchor_price: float) -> bool:
    """Updates strike's anchor price"""
    if anchor_price <= 0:
        print(f"[DB] ERR: Anchor price must be > 0. Got: {anchor_price}")
        return False
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE strikes SET anchor_price=? WHERE strike_id=?",
                (float(anchor_price), strike_id)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Strike {strike_id} anchor price updated to ₹{anchor_price:.2f}")
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_anchor_price() failed: {e}")
        return False


def update_strike_lots(strike_id: int, lots: int) -> bool:
    """Updates strike's lot count"""
    if lots < 1:
        print(f"[DB] ERR: Lots must be >= 1. Got: {lots}")
        return False
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE strikes SET lots=? WHERE strike_id=?",
                (int(lots), strike_id)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Strike {strike_id} lots updated to {lots}")
        return True
    except Exception as e:
        print(f"[DB] ERR update_strike_lots() failed: {e}")
        return False


def link_hedge(sell_strike_id: int, hedge_strike_id: int) -> bool:
    """
    Links a HEDGE_BUY strike to its paired SELL strike.
    Both are updated to reference each other.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?",
                (hedge_strike_id, sell_strike_id)
            )
            conn.execute(
                "UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?",
                (sell_strike_id, hedge_strike_id)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Hedge linked: Sell strike_id={sell_strike_id} ↔ Hedge strike_id={hedge_strike_id}")
        return True
    except Exception as e:
        print(f"[DB] ERR link_hedge() failed: {e}")
        return False


def unlink_hedge(strike_id: int) -> bool:
    """
    Removes the hedge_strike_id reference from a strike (sets it to NULL).
    Used during hedge rollover to detach the old hedge before re-linking to a new one.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                "UPDATE strikes SET hedge_strike_id=NULL WHERE strike_id=?",
                (strike_id,)
            )
            conn.commit()
            conn.close()
        print(f"[DB] OK Hedge unlinked: strike_id={strike_id}")
        return True
    except Exception as e:
        print(f"[DB] ERR unlink_hedge() failed: {e}")
        return False


def delete_strike(strike_id: int) -> bool:
    """Deletes a PENDING (not yet executed) strike + its legs."""
    strike = get_strike(strike_id)
    if not strike:
        print(f"[DB] ERR Strike {strike_id} not found.")
        return False
    if strike["status"] == "OPEN":
        print(f"[DB] BLOCKED Cannot delete strike {strike_id} -- status is OPEN (has live position).")
        return False
    try:
        with _lock:
            conn = _conn()
            conn.execute("DELETE FROM legs WHERE strike_id=?", (strike_id,))
            conn.execute("DELETE FROM strikes WHERE strike_id=?", (strike_id,))
            conn.commit()
            conn.close()
        print(f"[DB] OK Strike {strike_id} deleted.")
        return True
    except Exception as e:
        print(f"[DB] ERR delete_strike() failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ██████  LEGS CRUD (Live Position Tracking)
# ─────────────────────────────────────────────────────────────────────────────

def create_leg(strike_id: int, entry_price: float, order_id: str = "") -> int:
    """
    Creates a leg record on order fill (entry).
    Returns: leg_id or -1 on failure.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                """
                INSERT INTO legs (strike_id, entry_price, entry_time, order_id)
                VALUES (?, ?, ?, ?)
                """,
                (strike_id, entry_price, _ist_now(), order_id)
            )
            conn.commit()
            leg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
        # Mark strike as OPEN
        update_strike_status(strike_id, "OPEN")
        print(f"[DB] OK Leg created -> leg_id={leg_id} | Strike {strike_id} | Entry=₹{entry_price:.2f}")
        return leg_id
    except Exception as e:
        print(f"[DB] ERR create_leg() failed: {e}")
        return -1


def close_leg(leg_id: int, exit_price: float, realized_pnl: float) -> bool:
    """
    Closes a leg on exit. Records exit price, exit time, and realized P&L.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                """
                UPDATE legs
                SET exit_price=?, exit_time=?, realized_pnl=?
                WHERE leg_id=?
                """,
                (exit_price, _ist_now(), realized_pnl, leg_id)
            )
            conn.commit()
            # Get strike_id to update status
            cur = conn.execute("SELECT strike_id FROM legs WHERE leg_id=?", (leg_id,))
            row = cur.fetchone()
            conn.close()
        if row:
            update_strike_status(row["strike_id"], "CLOSED")
        print(f"[DB] OK Leg {leg_id} closed | Exit=₹{exit_price:.2f} | PnL=₹{realized_pnl:.2f}")
        return True
    except Exception as e:
        print(f"[DB] ERR close_leg() failed: {e}")
        return False


def get_leg(leg_id: int) -> dict:
    """Returns a single leg as dict, or {} if not found."""
    try:
        conn = _conn()
        cur = conn.execute("SELECT * FROM legs WHERE leg_id=?", (leg_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        print(f"[DB] ERR get_leg() failed: {e}")
        return {}


def get_legs_by_strike(strike_id: int) -> list:
    """Returns all legs for a strike as list of dicts."""
    try:
        conn = _conn()
        cur = conn.execute(
            "SELECT * FROM legs WHERE strike_id=? ORDER BY leg_id DESC",
            (strike_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] ERR get_legs_by_strike() failed: {e}")
        return []


def get_open_leg(strike_id: int) -> dict:
    """Returns the most recent open (not-yet-closed) leg for a strike."""
    try:
        conn = _conn()
        # An open leg has no exit_time set (empty string)
        cur = conn.execute(
            "SELECT * FROM legs WHERE strike_id=? AND (exit_time='' OR exit_time IS NULL) ORDER BY leg_id DESC LIMIT 1",
            (strike_id,)
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        print(f"[DB] ERR get_open_leg() failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# ██████  TRADES -- History Log
# ─────────────────────────────────────────────────────────────────────────────

def log_trade(
    block_id: int,
    strike_id: int,
    action: str,
    price: float,
    lots: int,
    order_status: str
) -> int:
    """
    Logs a trade action to history.
    action      : "ENTRY" / "EXIT" / "HEDGE_ENTRY" / "HEDGE_EXIT"
    Returns     : trade_id or -1 on failure.
    """
    try:
        with _lock:
            conn = _conn()
            conn.execute(
                """
                INSERT INTO trades (block_id, strike_id, action, price, lots, timestamp, order_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (block_id, strike_id, action.upper(), price, lots, _ist_now(), order_status)
            )
            conn.commit()
            trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
        print(
            f"[DB] 📝 Trade logged -> trade_id={trade_id} | "
            f"Block {block_id} | Strike {strike_id} | {action} | ₹{price:.2f} | {order_status}"
        )
        return trade_id
    except Exception as e:
        print(f"[DB] ERR log_trade() failed: {e}")
        return -1


def get_trades(block_id: int = None, limit: int = 100) -> list:
    """
    Returns trade history as list of dicts.
    block_id: filter by block -- or None for all trades.
    """
    try:
        conn = _conn()
        if block_id is not None:
            cur = conn.execute(
                "SELECT * FROM trades WHERE block_id=? ORDER BY trade_id DESC LIMIT ?",
                (block_id, limit)
            )
        else:
            cur = conn.execute(
                "SELECT * FROM trades ORDER BY trade_id DESC LIMIT ?",
                (limit,)
            )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] ERR get_trades() failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# ██████  P&L HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def calc_strike_pnl(strike: dict, current_ltp: float) -> float:
    """
    Calculates unrealized P&L for a single strike using blueprint formula.

    SELL LEG   : PnL = (Anchor Price - Current LTP) × Lots × LOT_SIZE
    HEDGE_BUY  : PnL = (Current LTP - Anchor Price) × Lots × LOT_SIZE

    Returns: P&L in ₹ (positive = profit, negative = loss)
    """
    lot_size = int(get("lot_size", str(cfg.NIFTY_LOT_SIZE)))
    anchor   = float(strike.get("anchor_price", 0.0))
    lots     = int(strike.get("lots", 1))
    leg_type = strike.get("leg_type", "SELL").upper()

    if leg_type == "SELL":
        return (anchor - current_ltp) * lots * lot_size
    elif leg_type == "HEDGE_BUY":
        return (current_ltp - anchor) * lots * lot_size
    return 0.0


def calc_block_pnl(block_id: int, ltp_map: dict) -> dict:
    """
    Calculates total P&L for a block.
    ltp_map: {strike_id: current_ltp} -- provided by pnl_engine.py

    Returns dict:
        {
          "block_id"   : int,
          "total_pnl"  : float,
          "strike_pnls": [{strike_id, strike_price, option_type, leg_type, pnl}]
        }
    """
    strikes   = get_strikes_by_block(block_id, status_filter="OPEN")
    total_pnl = 0.0
    details   = []

    for s in strikes:
        sid = s["strike_id"]
        ltp = ltp_map.get(sid, 0.0)
        pnl = calc_strike_pnl(s, ltp) if ltp > 0 else 0.0
        total_pnl += pnl
        details.append({
            "strike_id"   : sid,
            "strike_price": s["strike_price"],
            "option_type" : s["option_type"],
            "leg_type"    : s["leg_type"],
            "anchor_price": s["anchor_price"],
            "ltp"         : ltp,
            "lots"        : s["lots"],
            "pnl"         : round(pnl, 2),
        })

    return {
        "block_id"   : block_id,
        "total_pnl"  : round(total_pnl, 2),
        "strike_pnls": details,
    }


def calc_portfolio_pnl(ltp_map: dict) -> dict:
    """
    Calculates total portfolio P&L across all ACTIVE blocks.
    ltp_map: {strike_id: current_ltp}

    Returns dict:
        {
          "total_pnl"  : float,
          "block_pnls" : [calc_block_pnl results]
        }
    """
    active_blocks = get_all_blocks(status_filter="ACTIVE")
    total_pnl     = 0.0
    block_pnls    = []

    for block in active_blocks:
        bpnl = calc_block_pnl(block["block_id"], ltp_map)
        total_pnl += bpnl["total_pnl"]
        block_pnls.append(bpnl)

    return {
        "total_pnl" : round(total_pnl, 2),
        "block_pnls": block_pnls,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ██████  EXPIRY MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def check_and_expire_blocks() -> list:
    """
    Checks all ACTIVE blocks and auto-marks expired ones.
    A block is expired if its expiry_date is in the past.
    Returns: list of block_ids that were auto-expired.
    """
    from datetime import date
    expired_ids = []
    today       = date.today()

    active_blocks = get_all_blocks(status_filter="ACTIVE")
    for block in active_blocks:
        try:
            exp_date = datetime.strptime(block["expiry_date"], "%d-%b-%Y").date()
            if exp_date < today:
                update_block_status(block["block_id"], "EXPIRED")
                expired_ids.append(block["block_id"])
                print(f"[DB] EXPIRY Block {block['block_number']} auto-expired (Expiry: {block['expiry_date']})")
        except Exception as e:
            print(f"[DB] WARN  Could not parse expiry for block {block['block_id']}: {e}")

    return expired_ids


# ─────────────────────────────────────────────────────────────────────────────
# ██████  INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Initializes the database on startup:
    1. Creates all 5 tables (if not exist)
    2. Loads secrets from secrets.txt into memory
    3. Removes any accidentally stored secrets from SQLite
    4. Sets default settings if not already present
    """
    print("[DB] >> Initializing Zerodha OptionSelling database...")

    # 1. Create all tables
    conn = _conn()
    conn.close()
    print(f"[DB] OK All 5 tables verified -> {cfg.DB_PATH}")

    # 2. Load secrets from file into memory
    load_secrets()

    # 3. Scrub any secrets accidentally in SQLite (security)
    try:
        conn = _conn()
        placeholders = ",".join("?" for _ in SECRET_KEYS)
        conn.execute(
            f"DELETE FROM settings WHERE key IN ({placeholders})",
            tuple(SECRET_KEYS)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] WARN Secret scrub error: {e}")

    # 4. Default settings
    defaults = {
        "lot_size"             : str(cfg.NIFTY_LOT_SIZE),
        "algo_running"         : "ON",
        "paper_mode"           : "NO",
        "check_interval"       : str(cfg.DEFAULT_CHECK_INTERVAL),
        "hedge_distance"       : str(cfg.DEFAULT_HEDGE_DISTANCE),
        "buffer_tolerance"     : str(cfg.DEFAULT_BUFFER_TOLERANCE),
        "max_reentries_per_day": str(cfg.DEFAULT_MAX_REENTRIES_PER_DAY),
        "reentry_cooldown_sec" : str(cfg.DEFAULT_REENTRY_COOLDOWN_SEC),
        "reentry_discount_buffer": str(cfg.DEFAULT_REENTRY_DISCOUNT_BUFFER),
        "preferred_index"      : "NIFTY",
        "max_strikes_per_block": "50",
        "last_cycle_time"      : "",
        "comm_engine_running"  : "OFF",
        "comm_selected_contract": "",
        "comm_anchor_price"    : "0.0",
        "comm_lots"            : "1",
        "comm_position_state"  : "FLAT",
        "comm_entry_price"     : "0.0",
        "comm_entry_time"      : "",
        "comm_unrealized_pnl_pct": "0.0",
        "comm_stop_loss_pct"   : "0.0",
        "comm_carry_forward"   : "NO",
        "comm_last_check_candle_time": "",
    }
    for k, v in defaults.items():
        if not get(k):
            set(k, v)

    # ── Upgrade max_strikes_per_block from 5 to 50 if currently set to 5 ────
    if get("max_strikes_per_block") == "5":
        set("max_strikes_per_block", "50")
        print("[DB] UPGRADED max_strikes_per_block from 5 to 50")

    print("[DB] OK Zerodha OptionSelling DB initialized successfully.")
    print(f"[DB]    Paper Mode   : {get('paper_mode')}")
    print(f"[DB]    Lot Size     : {get('lot_size')}")
    print(f"[DB]    Algo Running : {get('algo_running')}")


# Auto-initialize on import
init_db()
