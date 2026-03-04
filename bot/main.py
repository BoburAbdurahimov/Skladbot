"""
Main Telegram bot: reply keyboard UI + step-by-step bulk entry.
Named sklads (Toxir, Kodir, Istam, Aziz) with 2 eni tables each (120, 100).

Flow:
  Main menu: [Prixod] [Rasxod] [Sklad]
  Sklad    → pick warehouse → send 2 images (Eni 120 + Eni 100)
  Prixod   → pick warehouse → pick eni → [qty → size]* → confirm batch
  Rasxod   → same but subtract
"""

from __future__ import annotations

from typing import Optional, Union

import os
import logging
from datetime import datetime, timedelta, timezone

TZ_TASHKENT = timezone(timedelta(hours=5))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from bot.states import (
    ConversationStep,
    OperationMode,
    ParsedItem,
    SKLADS,
    get_sklad_config,
    get_state,
    reset_state,
    start_operation,
    set_sklad,
    set_items,
)
from bot.parser import parse_input, format_confirmation
from bot.db import (
    apply_bulk_operation,
    get_matrix,
    get_daily_movements,
    ALLOWED_LENGTHS,
    ALLOWED_WIDTHS,
)
from bot.image import render_matrix

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ─── Keyboards ──────────────────────────────────────────────────────

def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Prixod"),
                KeyboardButton(text="Rasxod"),
            ],
            [
                KeyboardButton(text="Sklad"),
                KeyboardButton(text="Tarix"),
            ],
            [
                KeyboardButton(text="Tozalash"),
            ]
        ],
        resize_keyboard=True,
    )


# Build a set of all valid sklad button labels for matching
_SKLAD_LABELS = {f"{s.name} {s.eni}" for s in SKLADS}


def sklad_keyboard() -> ReplyKeyboardMarkup:
    buttons = []
    # 2 sklads per row
    for i in range(0, len(SKLADS), 2):
        row = []
        row.append(KeyboardButton(text=f"{SKLADS[i].name} {SKLADS[i].eni}"))
        if i + 1 < len(SKLADS):
            row.append(KeyboardButton(text=f"{SKLADS[i+1].name} {SKLADS[i+1].eni}"))
        buttons.append(row)
    buttons.append([KeyboardButton(text="Ortga")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Ortga")]],
        resize_keyboard=True,
    )


def tarix_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Bugun"), KeyboardButton(text="Kecha")],
            [KeyboardButton(text="Ortga")],
        ],
        resize_keyboard=True,
    )


def confirm_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Tasdiqlash", callback_data="confirm_batch"),
                InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_batch"),
            ]
        ]
    )


# ─── Size decoding & Date parsing ─────────────────────────────────

_VALID_SIZES = set()
for _l in ALLOWED_LENGTHS:
    for _w in ALLOWED_WIDTHS:
        _VALID_SIZES.add(_l + _w)


def decode_size(code: int) -> Optional[tuple[int, int]]:
    if code in _VALID_SIZES:
        length = (code // 100) * 100
        width = code % 100
        if length in ALLOWED_LENGTHS and width in ALLOWED_WIDTHS:
            return (length, width)
    return None


def parse_date_to_timestamps(date_txt: str) -> Optional[tuple[float, float]]:
    """Parse text ('Bugun', 'Kecha', 'dd.mm.yyyy') into start and end timestamps."""
    now = datetime.now(TZ_TASHKENT)
    text_lower = date_txt.lower()
    
    if text_lower == "bugun":
        target = now
    elif text_lower == "kecha":
        target = now - timedelta(days=1)
    else:
        try:
            target = datetime.strptime(date_txt, "%d.%m.%Y").replace(tzinfo=TZ_TASHKENT)
        except ValueError:
            return None
            
    start_dt = target.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(days=1)
    return start_dt.timestamp(), end_dt.timestamp()


# ─── /start ─────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message):
    reset_state(message.chat.id)
    await message.answer(
        "<b>Sklad Bot</b>\n\nQuyidagi tugmalardan birini tanlang:",
        reply_markup=main_keyboard(),
    )


# ─── Main menu buttons ─────────────────────────────────────────────

@router.message(F.text == "Prixod")
async def btn_prixod(message: Message):
    start_operation(message.chat.id, OperationMode.IN)
    await message.answer("<b>PRIXOD</b>\n\nQaysi skladga?", reply_markup=sklad_keyboard())


@router.message(F.text == "Rasxod")
async def btn_rasxod(message: Message):
    start_operation(message.chat.id, OperationMode.OUT)
    await message.answer("<b>RASXOD</b>\n\nQaysi skladdan?", reply_markup=sklad_keyboard())


@router.message(F.text == "Sklad")
async def btn_sklad(message: Message):
    state = get_state(message.chat.id)
    state.step = ConversationStep.WAITING_SKLAD_VIEW
    state.mode = None
    state.sklad_id = None
    state.items = []
    await message.answer("<b>Skladni tanlang:</b>", reply_markup=sklad_keyboard())


@router.message(F.text == "Tozalash")
async def btn_tozalash(message: Message):
    state = get_state(message.chat.id)
    state.step = ConversationStep.WAITING_SKLAD_CLEAR
    state.mode = None
    state.sklad_id = None
    state.items = []
    await message.answer("🧹 <b>Qaysi sklad ma'lumotlarini tozalash kerak?</b>", reply_markup=sklad_keyboard())


@router.message(F.text == "Tarix")
async def btn_tarix(message: Message):
    state = get_state(message.chat.id)
    state.step = ConversationStep.WAITING_DATE
    state.mode = None
    state.sklad_id = None
    state.items = []
    await message.answer(
        "<b>Tarix</b>\n\nQaysi kun bo'yicha hisobot kerak?\n\n"
        "Tugmalardan birini tanlang yoki sanani <code>kk.oo.yyyy</code> formatida kiriting (masalan: <b>04.03.2026</b>).",
        reply_markup=tarix_keyboard()
    )


# ─── Back / Cancel ──────────────────────────────────────────────────

@router.message(F.text == "Ortga")
async def btn_back(message: Message):
    reset_state(message.chat.id)
    await message.answer("Bosh menyu:", reply_markup=main_keyboard())


@router.message(F.text == "Bekor qilish")
async def btn_cancel(message: Message):
    reset_state(message.chat.id)
    await message.answer("<b>Bekor qilindi.</b>", reply_markup=main_keyboard())


# ─── Sklad selection ───────────────────────────────────────────────

@router.message(F.text.func(lambda t: t in _SKLAD_LABELS))
async def btn_sklad_pick(message: Message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.strip()

    # Find the sklad by matching "Name Eni" label
    sklad_num = None
    for s in SKLADS:
        if text == f"{s.name} {s.eni}":
            sklad_num = s.id
            break

    if sklad_num is None:
        await message.answer("Noto'g'ri sklad.", reply_markup=main_keyboard())
        return

    config = get_sklad_config(sklad_num)
    sklad_label = f"{config.name} {config.eni}" if config else f"Sklad {sklad_num}"

    if state.step == ConversationStep.WAITING_SKLAD_VIEW:
        await send_sklad_images(message, sklad_num)
        reset_state(chat_id)
        await message.answer("Bosh menyu:", reply_markup=main_keyboard())

    elif state.step == ConversationStep.WAITING_SKLAD_CLEAR:
        from bot.db import clear_sklad
        success = await clear_sklad(sklad_num)
        reset_state(chat_id)
        if success:
            await message.answer(f"✅ <b>{sklad_label} tozalandi!</b>", reply_markup=main_keyboard())
        else:
            await message.answer(f"❌ <b>Xatolik yuz berdi.</b>", reply_markup=main_keyboard())

    elif state.step == ConversationStep.WAITING_SKLAD_OP:
        set_sklad(chat_id, sklad_num)
        mode_label = "PRIXOD" if state.mode == OperationMode.IN else "RASXOD"
        await message.answer(
            f"<b>{sklad_label}</b> — {mode_label}",
            reply_markup=back_keyboard(),
        )
    else:
        await send_sklad_images(message, sklad_num)
        reset_state(chat_id)
        await message.answer("Bosh menyu:", reply_markup=main_keyboard())


# ─── Inline confirm/cancel callbacks ───────────────────────────────

@router.callback_query(F.data == "confirm_batch")
async def on_confirm(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    state = get_state(chat_id)

    if state.step != ConversationStep.WAITING_CONFIRM or not state.items:
        await callback.answer("Tasdiqlanadigan amal yo'q.", show_alert=True)
        return

    items = state.items
    sklad_id = state.sklad_id
    mode = state.mode

    success, msg = await apply_bulk_operation(sklad_id, mode, items)

    config = get_sklad_config(sklad_id)
    sklad_label = f"{config.name} {config.eni}" if config else f"Sklad {sklad_id}"
    reset_state(chat_id)

    if success:
        mode_label = "PRIXOD" if mode == OperationMode.IN else "RASXOD"
        total_qty = sum(i.qty for i in items)
        total_metr = sum((i.qty * (i.length + i.width)) / 100 for i in items)
        
        await callback.message.edit_text(
            f"<b>{mode_label} tasdiqlandi!</b>\n\n"
            f"{sklad_label}\n"
            f"{len(items)}/{total_qty}/{total_metr:g}\n\n"
            f"{msg}"
        )
    else:
        await callback.message.edit_text(f"<b>Rad etildi:</b>\n{msg}")

    await callback.answer()
    await callback.message.answer("Bosh menyu:", reply_markup=main_keyboard())


@router.callback_query(F.data == "cancel_batch")
async def on_cancel(callback: CallbackQuery):
    reset_state(callback.message.chat.id)
    await callback.message.edit_text("<b>Bekor qilindi.</b>")
    await callback.answer()
    await callback.message.answer("Bosh menyu:", reply_markup=main_keyboard())


# ─── Free-text handler (qty and size input) ─────────────────────────

@router.message(F.text)
async def handle_text(message: Message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.strip()

    # ─── Waiting for bulk text ───────────────────────────────────
    if state.step == ConversationStep.WAITING_BULK_TEXT:
        result = parse_input(text)

        if not result.items and not result.errors:
            await message.answer("Hech qanday ma'lumot topilmadi. Qaytadan urinib ko'ring yoki /start bosing.")
            return

        set_items(chat_id, result.items)
        state = get_state(chat_id)
        
        mode_label = "PRIXOD" if state.mode == OperationMode.IN else "RASXOD"
        conf_text = format_confirmation(result, mode_label)
        
        config = get_sklad_config(state.sklad_id)
        sklad_label = f"{config.name} {config.eni}" if config else f"Sklad {state.sklad_id}"

        # If there are items, we show confirm button. If only errors, None.
        markup = confirm_inline_keyboard() if result.items else None
        
        total_qty = sum(i.qty for i in result.items)
        total_metr = sum((i.qty * (i.length + i.width)) / 100 for i in result.items)
        tasdiq_matn = f"\n{len(result.items)}/{total_qty}/{total_metr:g}\nTasdiqlaysizmi?" if result.items else ""

        await message.answer(
            f"<b>{sklad_label}</b>\n\n"
            f"{conf_text}\n{tasdiq_matn}",
            reply_markup=markup,
        )
        return

    # ─── Waiting for date (Tarix) ────────────────────────────────
    if state.step == ConversationStep.WAITING_DATE:
        ts_range = parse_date_to_timestamps(text)
        if not ts_range:
            await message.answer("Noto'g'ri sana formati.\nMasalan: <code>04.03.2026</code> yoki quyidagi tugmalardan birini bosing:", reply_markup=tarix_keyboard())
            return
            
        start_ts, end_ts = ts_range
        movements = await get_daily_movements(start_ts, end_ts)
        
        if not movements:
            await message.answer(f"Bu sanada hech qanday harakat yo'q: <b>{text}</b>", reply_markup=main_keyboard())
            reset_state(chat_id)
            return
            
        lines = [f"<b>Harakatlar tarixi: {text}</b>\n"]
        for m in movements:
            config = get_sklad_config(m.sklad_id)
            s_name = f"{config.name} {config.eni}" if config else f"Sklad {m.sklad_id}"
            t_str = datetime.fromtimestamp(m.timestamp, TZ_TASHKENT).strftime("%H:%M")
            lines.append(f"<b>{s_name}</b> — {t_str}")
            lines.append(f"   <i>{m.details}</i>\n")
            
        # Send in chunks if very large, but usually fits
        response_text = "\n".join(lines)
        if len(response_text) > 4000:
            response_text = response_text[:4000] + "\n... (davomi bor)"
            
        await message.answer(response_text, reply_markup=main_keyboard())
        reset_state(chat_id)
        return

    # ─── Catch-all for active states ─────────────────────────────

    if state.step in [ConversationStep.WAITING_SKLAD_VIEW, ConversationStep.WAITING_SKLAD_OP, ConversationStep.WAITING_SKLAD_CLEAR]:
        await message.answer("Iltimos, quyidagi tugmalardan skladni tanlang:", reply_markup=sklad_keyboard())
        return

    # ─── Truly unknown input (e.g., when IDLE) ───────────────────
    reset_state(chat_id)
    await message.answer("Quyidagi tugmalardan birini tanlang:", reply_markup=main_keyboard())


# ─── Helper: send both eni images for a sklad ──────────────────────

async def send_sklad_images(message: Message, sklad_id: int):
    config = get_sklad_config(sklad_id)
    sklad_name = f"{config.name} {config.eni}" if config else f"Sklad {sklad_id}"
    try:
        matrix = await get_matrix(sklad_id)
        # Calculate total meters from all items in the matrix
        total_metr = sum(qty * (length + width) / 100 for (length, width), qty in matrix.items() if qty > 0)
        img_bytes = await render_matrix(matrix, sklad_id)
        photo = BufferedInputFile(img_bytes, filename=f"sklad_{sklad_id}.png")
        metr_text = f" — {total_metr:g}m" if total_metr > 0 else ""
        await message.answer_photo(
            photo=photo,
            caption=f"<b>{sklad_name}{metr_text}</b>",
        )
    except Exception as e:
        logger.exception("Error generating sklad image")
        await message.answer(f"Rasm yaratishda xatolik: {e}")
