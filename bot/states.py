"""
Chat state machine for the Sklad bot.
Multi-step conversation flow with bulk entry support.
Supports named sklads with 2 eni (width) sub-tables each.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─── Sklad configuration ────────────────────────────────────────────

@dataclass
class SkladConfig:
    """Configuration for a single warehouse."""
    id: int
    name: str
    corner_number: int  # number shown in top-left corner of image


SKLADS = [
    SkladConfig(id=1, name="Toxir", corner_number=15),
    SkladConfig(id=2, name="Kodir", corner_number=22),
    SkladConfig(id=3, name="Istam", corner_number=22),
    SkladConfig(id=4, name="Aziz", corner_number=15),
]

# Two sub-tables per sklad
ENI_VALUES = [120, 100]


def get_sklad_config(sklad_id: int) -> Optional[SkladConfig]:
    for s in SKLADS:
        if s.id == sklad_id:
            return s
    return None


# ─── Conversation enums ─────────────────────────────────────────────

class ConversationStep(Enum):
    IDLE = "idle"
    WAITING_SKLAD_VIEW = "view"
    WAITING_SKLAD_OP = "sklad_op"
    WAITING_ENI = "eni"            # Picking eni (120/100)
    WAITING_BULK_TEXT = "bulk_text"
    WAITING_MORE = "more"
    WAITING_CONFIRM = "confirm"
    WAITING_DATE = "date"          # Picking Tarix date


class OperationMode(Enum):
    IN = "in"
    OUT = "out"


@dataclass
class ParsedItem:
    qty: int
    length: int
    width: int


@dataclass
class ChatState:
    step: ConversationStep = ConversationStep.IDLE
    mode: Optional[OperationMode] = None
    sklad_id: Optional[int] = None
    eni: Optional[int] = None       # 120 or 100
    items: list[ParsedItem] = field(default_factory=list)


# ─── In-memory store ────────────────────────────────────────────────
_states: dict[int, ChatState] = {}


def get_state(chat_id: int) -> ChatState:
    if chat_id not in _states:
        _states[chat_id] = ChatState()
    return _states[chat_id]


def reset_state(chat_id: int) -> ChatState:
    _states[chat_id] = ChatState()
    return _states[chat_id]


def start_operation(chat_id: int, mode: OperationMode) -> ChatState:
    state = get_state(chat_id)
    state.step = ConversationStep.WAITING_SKLAD_OP
    state.mode = mode
    state.sklad_id = None
    state.eni = None
    state.items = []
    return state


def set_sklad(chat_id: int, sklad_id: int) -> ChatState:
    state = get_state(chat_id)
    state.sklad_id = sklad_id
    state.step = ConversationStep.WAITING_ENI
    return state


def set_eni(chat_id: int, eni: int) -> ChatState:
    state = get_state(chat_id)
    state.eni = eni
    state.step = ConversationStep.WAITING_BULK_TEXT
    return state


def set_items(chat_id: int, items: list[ParsedItem]) -> ChatState:
    state = get_state(chat_id)
    state.items = items
    state.step = ConversationStep.WAITING_CONFIRM
    return state


def format_items_summary(state: ChatState) -> str:
    lines = []
    for idx, item in enumerate(state.items, 1):
        code = item.length + item.width
        lines.append(f"  {idx}. <b>{item.qty}</b> ta — {item.length}×{item.width} ({code})")
    return "\n".join(lines)
