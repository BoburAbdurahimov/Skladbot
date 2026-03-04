"""
Tests for size decoding and parser logic.
Run with: pytest tests/test_parser.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.parser import parse_input, _decode_size, _normalize
from bot.states import ParsedItem


# ─── Size Decoding ──────────────────────────────────────────────────

class TestSizeDecoding:
    """Test the size encoding rule: 680 -> (600, 80)."""

    def test_670(self):
        assert _decode_size(670) == (600, 70)

    def test_740(self):
        assert _decode_size(740) == (700, 40)

    def test_200(self):
        assert _decode_size(200) == (200, 0)

    def test_350(self):
        assert _decode_size(350) == (300, 50)

    def test_490(self):
        assert _decode_size(490) == (400, 90)

    def test_invalid_size_150(self):
        assert _decode_size(150) is None

    def test_invalid_size_805(self):
        assert _decode_size(805) is None

    def test_invalid_size_999(self):
        assert _decode_size(999) is None

    def test_all_valid_sizes(self):
        from bot.db import ALLOWED_LENGTHS, ALLOWED_WIDTHS
        for l in ALLOWED_LENGTHS:
            for w in ALLOWED_WIDTHS:
                encoded = l + w
                result = _decode_size(encoded)
                assert result == (l, w), f"Failed for {encoded}"


# ─── Normalization ──────────────────────────────────────────────────

class TestNormalization:
    def test_unicode_multiply(self):
        assert "x" in _normalize("600×80")

    def test_comma_replacement(self):
        result = _normalize("5, 680")
        assert "," not in result

    def test_semicolon_replacement(self):
        result = _normalize("5;680")
        assert ";" not in result

    def test_collapse_spaces(self):
        result = _normalize("5   ta   680")
        assert "   " not in result


# ─── Size Decoding from main module ─────────────────────────────────

class TestMainSizeDecoding:
    """Test the decode_size function in main.py."""

    def test_decode_680(self):
        from bot.main import decode_size
        result = decode_size(680)
        assert result == (600, 80)

    def test_decode_740(self):
        from bot.main import decode_size
        result = decode_size(740)
        assert result == (700, 40)

    def test_decode_200(self):
        from bot.main import decode_size
        result = decode_size(200)
        assert result == (200, 0)

    def test_decode_invalid(self):
        from bot.main import decode_size
        assert decode_size(150) is None
        assert decode_size(805) is None
        assert decode_size(999) is None


# ─── Parser single-line (still available for bulk) ───────────────────

class TestSingleLineParsing:
    def _parse_one(self, text: str) -> ParsedItem | None:
        result = parse_input(text)
        if result.items:
            return result.items[0]
        return None

    def test_qty_ta_size(self):
        item = self._parse_one("5 ta 680")
        assert item is not None
        assert item.qty == 5
        assert item.length == 600
        assert item.width == 80

    def test_size_then_qty(self):
        item = self._parse_one("680 5")
        assert item is not None
        assert item.qty == 5
        assert item.length == 600
        assert item.width == 80

    def test_qty_length_x_width(self):
        item = self._parse_one("5 600x80")
        assert item is not None
        assert item.qty == 5
        assert item.length == 600
        assert item.width == 80

    def test_qty_length_width(self):
        item = self._parse_one("5 600 80")
        assert item is not None
        assert item.qty == 5
        assert item.length == 600
        assert item.width == 80


# ─── Mode Detection ─────────────────────────────────────────────────

class TestModeDetection:
    def test_kirim_trigger(self):
        result = parse_input("kirim")
        assert result.detected_mode == "in"

    def test_chiqim_trigger(self):
        result = parse_input("chiqim")
        assert result.detected_mode == "out"

    def test_plus_trigger(self):
        result = parse_input("+")
        assert result.detected_mode == "in"

    def test_minus_trigger(self):
        result = parse_input("-")
        assert result.detected_mode == "out"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
