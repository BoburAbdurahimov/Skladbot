"""
Database layer for the Sklad bot.
Uses Turso (libsql-client) for persistent cloud storage.
4 named warehouses, Lengths: 200-800, Widths: 0-90.
"""

from __future__ import annotations

import os
import time
import asyncio
from dataclasses import dataclass

import libsql_client

from bot.states import ParsedItem, OperationMode, SKLADS

@dataclass
class MovementLog:
    sklad_id: int
    operation: str
    details: str
    timestamp: float

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

ALLOWED_LENGTHS = [200, 300, 400, 500, 600, 700, 800]
ALLOWED_WIDTHS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
SKLAD_COUNT = len(SKLADS)


def _get_conn():
    """Get a connection to the Turso database."""
    # Use the synchronous client for simplicity and thread safety
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)


def _init_db(conn):
    """Create tables and seed inventory rows if needed."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sklad_id INTEGER NOT NULL,
            length   INTEGER NOT NULL,
            width    INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            UNIQUE(sklad_id, length, width)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movements (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sklad_id  INTEGER NOT NULL,
            operation TEXT    NOT NULL,
            details   TEXT    NOT NULL,
            timestamp REAL    NOT NULL
        )
    """)
    for s in SKLADS:
        for l in ALLOWED_LENGTHS:
            for w in ALLOWED_WIDTHS:
                conn.execute(
                    "INSERT OR IGNORE INTO inventory (sklad_id, length, width, quantity) VALUES (?, ?, ?, 0)",
                    [s.id, l, w],
                )


# Initialize on import
_conn = _get_conn()
_init_db(_conn)


async def get_matrix(sklad_id: int) -> dict[tuple[int, int], int]:
    def _query():
        rs = _conn.execute(
            "SELECT length, width, quantity FROM inventory WHERE sklad_id=? ORDER BY length, width",
            [sklad_id],
        )
        return {(r[0], r[1]): r[2] for r in rs.rows}
    return await asyncio.to_thread(_query)


async def apply_bulk_operation(
    sklad_id: int,
    mode: OperationMode,
    items: list[ParsedItem],
) -> tuple[bool, str]:
    def _execute():
        try:
            if mode == OperationMode.OUT:
                for item in items:
                    rs = _conn.execute(
                        "SELECT quantity FROM inventory WHERE sklad_id=? AND length=? AND width=?",
                        [sklad_id, item.length, item.width],
                    )
                    
                    current = rs.rows[0][0] if rs.rows else 0
                    if current < item.qty:
                        return (
                            False,
                            f"Yetarli emas: {item.length}×{item.width} da "
                            f"faqat {current} ta bor, {item.qty} ta so'ralmoqda.",
                        )

            sign = 1 if mode == OperationMode.IN else -1
            details_parts = []
            
            # Using a transaction to ensure atomic bulk insert
            stmts = []
            for item in items:
                delta = item.qty * sign
                stmts.append(
                    libsql_client.Statement(
                        """
                        INSERT INTO inventory (sklad_id, length, width, quantity)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(sklad_id, length, width) DO UPDATE SET quantity = quantity + ?
                        """,
                        [sklad_id, item.length, item.width, max(0, delta), delta]
                    )
                )
                op_label = "+" if sign > 0 else "-"
                details_parts.append(f"{op_label}{item.qty} {item.length}x{item.width}")

            op_name = "PRIXOD" if mode == OperationMode.IN else "RASXOD"
            stmts.append(
                libsql_client.Statement(
                    "INSERT INTO movements (sklad_id, operation, details, timestamp) VALUES (?, ?, ?, ?)",
                    [sklad_id, op_name, "; ".join(details_parts), time.time()]
                )
            )

            _conn.execute_batch(stmts)

            total_qty = sum(i.qty for i in items)
            total_metr = sum((i.qty * (i.length + i.width)) / 100 for i in items)
            return (True, f"Muvaffaqiyatli saqlandi! ({len(items)}/{total_qty}/{total_metr:g})")
        except Exception as e:
            return (False, f"Xatolik: {e}")

    return await asyncio.to_thread(_execute)


async def get_daily_movements(start_ts: float, end_ts: float) -> list[MovementLog]:
    """Fetch movement logs within a time range."""
    def _query():
        rs = _conn.execute(
            "SELECT sklad_id, operation, details, timestamp FROM movements "
            "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC",
            [start_ts, end_ts],
        )
        return [MovementLog(*r) for r in rs.rows]
    return await asyncio.to_thread(_query)


async def clear_sklad(sklad_id: int) -> bool:
    """Reset inventory to 0 and delete movement logs for a specific sklad_id."""
    def _execute():
        try:
            _conn.execute_batch([
                libsql_client.Statement(
                    "UPDATE inventory SET quantity = 0 WHERE sklad_id=?", 
                    [sklad_id]
                ),
                libsql_client.Statement(
                    "DELETE FROM movements WHERE sklad_id=?", 
                    [sklad_id]
                ),
                libsql_client.Statement(
                    "INSERT INTO movements (sklad_id, operation, details, timestamp) VALUES (?, ?, ?, ?)",
                    [sklad_id, "CLEAR", "Ombor tozalandi", time.time()]
                )
            ])
            return True
        except Exception:
            return False
    return await asyncio.to_thread(_execute)
