"""
Image renderer for warehouse inventory matrix.
White bg, red headers, purple cell values, corner number + eni label.
"""

from __future__ import annotations

from typing import Optional, Union

import io
from PIL import Image, ImageDraw, ImageFont

from bot.db import ALLOWED_LENGTHS, ALLOWED_WIDTHS
from bot.states import get_sklad_config


import os

def _get_font(size: int, bold: bool = False) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    font_path = os.path.join(os.path.dirname(__file__), "Roboto-Bold.ttf")
    try:
        return ImageFont.truetype(font_path, size)
    except (IOError, OSError):
        # Fallback to defaults if somehow missing during dev
        return ImageFont.load_default()


async def render_matrix(matrix: dict[tuple[int, int], int], sklad_id: int) -> bytes:
    """
    Render the inventory matrix as PNG.
    Shows config.name and eni in title area.
    """
    config = get_sklad_config(sklad_id)
    corner_number = config.corner_number if config else sklad_id
    sklad_name = config.name if config else f"Sklad {sklad_id}"

    lengths = ALLOWED_LENGTHS
    widths = ALLOWED_WIDTHS

    cell_w = 85
    cell_h = 65
    header_h = cell_h
    header_w = cell_w

    total_w = header_w + len(widths) * cell_w + 2
    total_h = header_h + len(lengths) * cell_h + 2

    bg_color = (255, 255, 255)
    grid_color = (0, 0, 0)
    header_text_color = (220, 0, 0)
    cell_text_color = (90, 50, 140)
    corner_color = (0, 0, 0)

    img = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(img)

    font_header = _get_font(34, bold=True)
    font_cell = _get_font(30, bold=True)
    font_corner = _get_font(42, bold=True)

    # ─── Corner number in top-left cell ──────────────────────────
    corner_label = str(corner_number)
    bbox = draw.textbbox((0, 0), corner_label, font=font_corner)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (1 + (header_w - tw) // 2, 1 + (header_h - th) // 2),
        corner_label,
        fill=corner_color,
        font=font_corner,
    )

    # ─── Column headers (widths) ─────────────────────────────────
    for j, w in enumerate(widths):
        x = 1 + header_w + j * cell_w
        label = str(w)
        bbox = draw.textbbox((0, 0), label, font=font_header)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (x + (cell_w - tw) // 2, 1 + (header_h - th) // 2),
            label,
            fill=header_text_color,
            font=font_header,
        )

    # ─── Row headers + data cells ────────────────────────────────
    for i, l in enumerate(lengths):
        y = 1 + header_h + i * cell_h

        label = str(l)
        bbox = draw.textbbox((0, 0), label, font=font_header)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (1 + (header_w - tw) // 2, y + (cell_h - th) // 2),
            label,
            fill=header_text_color,
            font=font_header,
        )

        for j, w in enumerate(widths):
            x = 1 + header_w + j * cell_w
            qty = matrix.get((l, w), 0)

            if qty > 0:
                text = str(qty)
                bbox = draw.textbbox((0, 0), text, font=font_cell)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text(
                    (x + (cell_w - tw) // 2, y + (cell_h - th) // 2),
                    text,
                    fill=cell_text_color,
                    font=font_cell,
                )

    # ─── Grid lines ──────────────────────────────────────────────
    for i in range(len(lengths) + 2):
        y = 1 + i * cell_h
        draw.line([(0, y), (total_w, y)], fill=grid_color, width=2)
    for j in range(len(widths) + 2):
        x = 1 + j * cell_w
        draw.line([(x, 0), (x, total_h)], fill=grid_color, width=2)

    draw.rectangle([0, 0, total_w - 1, total_h - 1], outline=grid_color, width=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
