"""
Free-form text parser for warehouse inventory input.
Handles many messy input formats, extracts (qty, length, width) triples.
"""

from __future__ import annotations

from typing import Optional, Union

import re
from dataclasses import dataclass, field

from bot.db import ALLOWED_LENGTHS, ALLOWED_WIDTHS
from bot.states import ParsedItem

# All valid encoded sizes: e.g. 200, 210, ..., 790
_VALID_SIZES = set()
for _l in ALLOWED_LENGTHS:
    for _w in ALLOWED_WIDTHS:
        _VALID_SIZES.add(_l + _w)

# Mode trigger words
KIRIM_TRIGGERS = {"kirim", "prixod", "+", "add", "приход", "кирим"}
CHIQIM_TRIGGERS = {"chiqim", "rashod", "-", "minus", "sell", "расход", "чиким"}
HOLAT_TRIGGERS = {"holat", "status", "ombor", "inventory", "холат", "омбор", "статус"}


@dataclass
class ParseResult:
    """Result of parsing a multi-line input."""
    items: list[ParsedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    detected_mode: Optional[str] = None  # "in", "out", or None


def _normalize(text: str) -> str:
    """Normalize input text for easier parsing."""
    text = text.strip().lower()
    # Replace unicode multiplication sign and Cyrillic 'х'
    text = text.replace("×", "x").replace("*", "x").replace("х", "x")
    
    # Convert '4.70' or '4,70' or '4 . 70' to '470'
    # Also handles '4.7' -> '470' (adds missing zero)
    def fix_decimal(match):
        d1 = match.group(1)
        d2 = match.group(2)
        if len(d2) == 1:
            d2 += "0"
        return d1 + d2
    text = re.sub(r'(\d)\s*[.,]\s*(\d+)', fix_decimal, text)

    # Remove common unit words (ta, шт, dona, pcs, дана, sht, штук)
    text = re.sub(r'\b(ta|sht|шт|штук|dona|дана|pcs|pc|piece|pieces)\b', ' ', text)
    # Replace separators with space
    text = re.sub(r'[,;:=]', ' ', text)
    # Remove emoji and non-alphanumeric except newline, space, +, -, x, .
    text = re.sub(r'[^\w\s+\-x.\n]', ' ', text)
    # Collapse whitespace (but keep newlines)
    lines = text.split('\n')
    lines = [re.sub(r'[ \t]+', ' ', line.strip()) for line in lines]
    return '\n'.join(lines)


def _decode_size(size: int) -> Optional[tuple[int, int]]:
    """
    Decode a single encoded size number to (length, width).
    E.g. 680 -> (600, 80), 740 -> (700, 40).
    """
    if size in _VALID_SIZES:
        length = (size // 100) * 100
        width = size % 100
        if length in ALLOWED_LENGTHS and width in ALLOWED_WIDTHS:
            return (length, width)
    return None


def _is_valid_length(n: int) -> bool:
    return n in ALLOWED_LENGTHS


def _is_valid_width(n: int) -> bool:
    return n in ALLOWED_WIDTHS


def _is_valid_size(n: int) -> bool:
    """Check if n is a valid encoded size (3-digit combination)."""
    return n in _VALID_SIZES


def _detect_mode_in_line(line: str) -> Optional[str]:
    """Check if a line contains a mode trigger word. Returns 'in', 'out', or None."""
    words = set(re.findall(r'[a-zA-Zа-яА-ЯёЁ+\-]+', line))
    for w in words:
        wl = w.lower()
        if wl in KIRIM_TRIGGERS:
            return "in"
        if wl in CHIQIM_TRIGGERS:
            return "out"
    return None


def _parse_line(line: str, line_num: int) -> tuple[Optional[ParsedItem], Optional[str]]:
    """
    Parse a single line to extract (qty, length, width).
    Returns (ParsedItem, None) on success or (None, error_message) on failure.
    """
    # Check for explicit "length x width" pattern first
    lxw_match = re.search(r'(\d+)\s*x\s*(\d+)', line)
    explicit_length = None
    explicit_width = None

    if lxw_match:
        l_val, w_val = int(lxw_match.group(1)), int(lxw_match.group(2))
        if _is_valid_length(l_val) and _is_valid_width(w_val):
            explicit_length = l_val
            explicit_width = w_val
            # Remove the "LxW" part and find qty in the rest
            rest = line[:lxw_match.start()] + line[lxw_match.end():]
            rest_nums = [int(x) for x in re.findall(r'\d+', rest)]
            if len(rest_nums) == 1:
                qty = rest_nums[0]
                if qty > 0:
                    return (ParsedItem(qty=qty, length=explicit_length, width=explicit_width), None)
                else:
                    return (None, f"#{line_num}: Miqdor 0 dan katta bo'lishi kerak")
            elif len(rest_nums) == 0:
                return (None, f"#{line_num}: Miqdor topilmadi: '{line.strip()}'")
            else:
                # Try first number as qty
                qty = rest_nums[0]
                if qty > 0:
                    return (ParsedItem(qty=qty, length=explicit_length, width=explicit_width), None)
                return (None, f"#{line_num}: Noaniq format: '{line.strip()}'")

    # Extract all integers
    numbers = [int(x) for x in re.findall(r'\d+', line)]

    if len(numbers) == 0:
        return (None, None)  # empty/header line, skip silently

    if len(numbers) == 1:
        # Single number – can't determine qty and size both
        return (None, f"#{line_num}: Bitta raqam yetarli emas: '{line.strip()}'")

    if len(numbers) == 2:
        a, b = numbers
        return _resolve_two_numbers(a, b, line, line_num)

    if len(numbers) == 3:
        return _resolve_three_numbers(numbers, line, line_num)

    # 4+ numbers: try to find valid trio
    return _resolve_many_numbers(numbers, line, line_num)


def _resolve_two_numbers(
    a: int, b: int, line: str, line_num: int
) -> tuple[Optional[ParsedItem], Optional[str]]:
    """Resolve two numbers into (qty, size) or (size, qty)."""
    a_is_size = _is_valid_size(a)
    b_is_size = _is_valid_size(b)

    if a_is_size and b_is_size:
        # Both look like sizes – ambiguous, can't decide
        return (None, f"#{line_num}: Ikki raqam ham o'lchamga o'xshaydi, miqdor topilmadi: '{line.strip()}'")

    if a_is_size and not b_is_size:
        # a = size, b = qty
        size_decoded = _decode_size(a)
        if size_decoded and b > 0:
            return (ParsedItem(qty=b, length=size_decoded[0], width=size_decoded[1]), None)

    if b_is_size and not a_is_size:
        # a = qty, b = size
        size_decoded = _decode_size(b)
        if size_decoded and a > 0:
            return (ParsedItem(qty=a, length=size_decoded[0], width=size_decoded[1]), None)

    # Neither is a valid encoded size
    # Check if one is a valid length and other is qty (width=0)
    a_is_length = _is_valid_length(a)
    b_is_length = _is_valid_length(b)

    if a_is_length and not b_is_length:
        # Maybe a=length, b=qty, width=0? But this is ambiguous.
        # Or a=length, b=width? Then qty is missing.
        if _is_valid_width(b):
            return (None, f"#{line_num}: O'lcham topildi ({a}x{b}), lekin miqdor yo'q: '{line.strip()}'")
        # b might be qty, size=a00 (width=0)
        if b > 0:
            return (ParsedItem(qty=b, length=a, width=0), None)

    if b_is_length and not a_is_length:
        if _is_valid_width(a):
            return (None, f"#{line_num}: O'lcham topildi ({b}x{a}), lekin miqdor yo'q: '{line.strip()}'")
        if a > 0:
            return (ParsedItem(qty=a, length=b, width=0), None)

    # Try length in meters (e.g. 11 Ta 4 means qty 11, length 400, width 0)
    if b * 100 in ALLOWED_LENGTHS and a > 0:
        return (ParsedItem(qty=a, length=b * 100, width=0), None)
        
    if a * 100 in ALLOWED_LENGTHS and b > 0:
        return (ParsedItem(qty=b, length=a * 100, width=0), None)

    return (None, f"#{line_num}: Raqamlar tushunarsiz: '{line.strip()}'")


def _resolve_three_numbers(
    nums: list[int], line: str, line_num: int
) -> tuple[Optional[ParsedItem], Optional[str]]:
    """
    Resolve three numbers: could be [qty, length, width] or [length, width, qty].
    """
    a, b, c = nums

    # Try [qty, length, width]
    if _is_valid_length(b) and _is_valid_width(c) and a > 0:
        return (ParsedItem(qty=a, length=b, width=c), None)

    # Try [length, width, qty]
    if _is_valid_length(a) and _is_valid_width(b) and c > 0:
        return (ParsedItem(qty=c, length=a, width=b), None)

    # Try [qty, length_in_meters, width_in_cm] (e.g. typing "7 4 70" instead of 4.70)
    if b * 100 in ALLOWED_LENGTHS and _is_valid_width(c) and a > 0:
        return (ParsedItem(qty=a, length=b * 100, width=c), None)

    # Try [length_in_meters, width_in_cm, qty]
    if a * 100 in ALLOWED_LENGTHS and _is_valid_width(b) and c > 0:
        return (ParsedItem(qty=c, length=a * 100, width=b), None)

    # Try [qty, size_encoded] where size is one of them
    # a=qty, b+c encoded? No – try each as encoded size
    for i, n in enumerate(nums):
        decoded = _decode_size(n)
        if decoded:
            remaining = [nums[j] for j in range(3) if j != i]
            # remaining should have 1 that looks like qty
            qtys = [r for r in remaining if r > 0 and not _is_valid_size(r)]
            if len(qtys) == 1:
                return (ParsedItem(qty=qtys[0], length=decoded[0], width=decoded[1]), None)

    return (None, f"#{line_num}: 3 ta raqam tushunarsiz: '{line.strip()}'")


def _resolve_many_numbers(
    nums: list[int], line: str, line_num: int
) -> tuple[Optional[ParsedItem], Optional[str]]:
    """Try to find a valid (qty, length, width) among 4+ numbers."""
    # Strategy: look for longest×width pattern
    for i in range(len(nums)):
        if _is_valid_length(nums[i]):
            for j in range(len(nums)):
                if j != i and _is_valid_width(nums[j]):
                    for k in range(len(nums)):
                        if k != i and k != j and nums[k] > 0:
                            return (
                                ParsedItem(qty=nums[k], length=nums[i], width=nums[j]),
                                None,
                            )

    # Try encoded sizes
    for i in range(len(nums)):
        decoded = _decode_size(nums[i])
        if decoded:
            for j in range(len(nums)):
                if j != i and nums[j] > 0 and not _is_valid_size(nums[j]):
                    return (
                        ParsedItem(qty=nums[j], length=decoded[0], width=decoded[1]),
                        None,
                    )

    return (None, f"#{line_num}: Ko'p raqamlar, tushunarsiz: '{line.strip()}'")


def parse_input(text: str) -> ParseResult:
    """
    Parse a full multi-line input block.
    Detects mode triggers, extracts items, collects errors.
    """
    result = ParseResult()
    normalized = _normalize(text)
    lines = normalized.split('\n')

    for i, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        # Check for mode trigger
        mode = _detect_mode_in_line(line)
        if mode:
            result.detected_mode = mode
            # If the line is ONLY a trigger word (no numbers), skip parsing it
            nums_in_line = re.findall(r'\d+', line)
            if not nums_in_line:
                continue

        # Remove any leading +/- sign that was part of the format
        clean_line = re.sub(r'^[+\-]\s*', '', line)

        item, error = _parse_line(clean_line, i)
        if item:
            result.items.append(item)
        elif error:
            result.errors.append(error)

    return result


def format_confirmation(result: ParseResult, mode_label: str) -> str:
    """Format a confirmation message for the parsed result."""
    lines = []
    lines.append(f"📋 <b>Tasdiqlov ({mode_label})</b>\n")

    if result.items:
        lines.append(f"✅ Topilgan qatorlar: <b>{len(result.items)}</b>")
        lines.append("─" * 28)
        for idx, item in enumerate(result.items, 1):
            arrow = "📥" if mode_label == "KIRIM" else "📤"
            lines.append(f"  {arrow} {idx}. <b>{item.qty}</b> ta — {item.length}×{item.width}")
        lines.append("─" * 28)

    if result.errors:
        lines.append(f"\n⚠️ Xatolar: <b>{len(result.errors)}</b>")
        for err in result.errors:
            lines.append(f"  🔸 {err}")

    if not result.items:
        lines.append("\n❌ Hech qanday ma'lumot topilmadi.")

    return "\n".join(lines)
