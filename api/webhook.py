"""
Vercel serverless webhook handler (BaseHTTPRequestHandler format).
Receives Telegram webhook POST requests and routes them to the aiogram dispatcher.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import logging
from http.server import BaseHTTPRequestHandler

# Ensure the project root is in sys.path so we can import `bot.*`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set DB path to /tmp for Vercel
os.environ.setdefault("SKLAD_DB_PATH", "/tmp/sklad.db")

logger = logging.getLogger(__name__)

# Load bot token safely
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

# Pre-initialize dispatcher and bot
from bot.main import dp

TOKEN = os.environ.get("BOT_TOKEN", "dummy_token_to_prevent_crash_during_import")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def feed_update(body_dict: dict):
    try:
        update = Update.model_validate(body_dict, context={"bot": bot})
        await dp.feed_update(bot, update)
    finally:
        # Vercel serverless requires explicitly closing aiohttp sessions
        # otherwise subsequent requests hang
        await bot.session.close()
class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler."""

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "bot": "sklad-bot"}).encode())
        return

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))

            # Run async update
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(feed_update(body))
            finally:
                loop.close()

            # Always respond 200 OK so Telegram doesn't retry
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            logger.exception(f"Error processing update: {e}")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
