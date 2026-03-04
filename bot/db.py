"""
Database layer for the Sklad bot.
4 named warehouses × 2 eni tables (120, 100) per sklad.
Lengths: 200-800, Widths: 0-90.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
import aiosqlite

from bot.states import ParsedItem, OperationMode, SKLADS

@dataclass
class MovementLog:
    sklad_id: int
    operation: str
    details: str
    timestamp: float

DB_PATH = os.environ.get("SKLAD_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "sklad.db"))

ALLOWED_LENGTHS = [200, 300, 400, 500, 600, 700, 800]
ALLOWED_WIDTHS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
SKLAD_COUNT = len(SKLADS)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            sklad_id INTEGER NOT NULL,
            length   INTEGER NOT NULL,
            width    INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            UNIQUE(sklad_id, length, width)
        );
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movements (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sklad_id  INTEGER NOT NULL,
            operation TEXT    NOT NULL,
            details   TEXT    NOT NULL,
            timestamp REAL    NOT NULL
        );
    """)
    for s in SKLADS:
        for l in ALLOWED_LENGTHS:
            for w in ALLOWED_WIDTHS:
                await db.execute(
                    "INSERT OR IGNORE INTO inventory (sklad_id, length, width, quantity) VALUES (?, ?, ?, 0)",
                    (s.id, l, w),
                )
    await db.commit()
    return db


async def get_matrix(sklad_id: int) -> dict[tuple[int, int], int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT length, width, quantity FROM inventory WHERE sklad_id=? ORDER BY length, width",
            (sklad_id,),
        )
        rows = await cursor.fetchall()
        return {(r[0], r[1]): r[2] for r in rows}
    finally:
        await db.close()


async def apply_bulk_operation(
    sklad_id: int,
    mode: OperationMode,
    items: list[ParsedItem],
) -> tuple[bool, str]:
    db = await get_db()
    try:
        if mode == OperationMode.OUT:
            for item in items:
                cursor = await db.execute(
                    "SELECT quantity FROM inventory WHERE sklad_id=? AND length=? AND width=?",
                    (sklad_id, item.length, item.width),
                )
                row = await cursor.fetchone()
                current = row[0] if row else 0
                if current < item.qty:
                    return (
                        False,
                        f"Yetarli emas: {item.length}×{item.width} da "
                        f"faqat {current} ta bor, {item.qty} ta so'ralmoqda.",
                    )

        sign = 1 if mode == OperationMode.IN else -1
        details_parts = []
        for item in items:
            delta = item.qty * sign
            await db.execute(
                """
                INSERT INTO inventory (sklad_id, length, width, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sklad_id, length, width) DO UPDATE SET quantity = quantity + ?
                """,
                (sklad_id, item.length, item.width, max(0, delta), delta),
            )
            op_label = "+" if sign > 0 else "-"
            details_parts.append(f"{op_label}{item.qty} {item.length}x{item.width}")

        op_name = "PRIXOD" if mode == OperationMode.IN else "RASXOD"
        await db.execute(
            "INSERT INTO movements (sklad_id, operation, details, timestamp) VALUES (?, ?, ?, ?)",
            (sklad_id, op_name, "; ".join(details_parts), time.time()),
        )

        await db.commit()
        total_qty = sum(i.qty for i in items)
        total_metr = sum((i.qty * (i.length + i.width)) / 100 for i in items)
        return (True, f"Muvaffaqiyatli saqlandi! ({len(items)}/{total_qty}/{total_metr:g})")
    except Exception as e:
        await db.rollback()
        return (False, f"Xatolik: {e}")
    finally:
        await db.close()


async def get_daily_movements(start_ts: float, end_ts: float) -> list[MovementLog]:
    """Fetch movement logs within a time range."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT sklad_id, operation, details, timestamp FROM movements "
            "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC",
            (start_ts, end_ts),
        )
        rows = await cursor.fetchall()
        return [MovementLog(*r) for r in rows]
    finally:
        await db.close()


async def clear_sklad(sklad_id: int) -> bool:
    """Reset inventory to 0 and delete movement logs for a specific sklad_id."""
    db = await get_db()
    try:
        await db.execute("UPDATE inventory SET quantity = 0 WHERE sklad_id=?", (sklad_id,))
        await db.execute("DELETE FROM movements WHERE sklad_id=?", (sklad_id,))
        await db.execute(
            "INSERT INTO movements (sklad_id, operation, details, timestamp) VALUES (?, ?, ?, ?)",
            (sklad_id, "CLEAR", "Ombor tozalandi", time.time()),
        )
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        return False
    finally:
        await db.close()
