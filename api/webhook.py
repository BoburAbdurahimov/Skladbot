"""
Vercel serverless webhook handler.
Receives Telegram webhook POST requests and routes them to the aiogram dispatcher.

Deploy to Vercel and set the webhook:
  https://api.telegram.org/bot<TOKEN>/setWebhook?url=<VERCEL_URL>/api/webhook
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import logging

# Ensure the project root is in sys.path so we can import `bot.*`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set DB path to /tmp for Vercel
os.environ.setdefault("SKLAD_DB_PATH", "/tmp/sklad.db")

from aiogram.types import Update
from bot.main import bot, dp

logger = logging.getLogger(__name__)


async def _process_update(body: dict) -> None:
    """Feed a raw update dict into the aiogram dispatcher."""
    update = Update.model_validate(body, context={"bot": bot})
    await dp.feed_update(bot, update)


def handler(request, response):
    """
    Vercel Python serverless function handler.
    Expects POST requests with JSON body from Telegram.

    Compatible with Vercel Python Runtime (vercel-python).
    """
    if request.method == "GET":
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"status": "ok", "bot": "sklad-bot"}).encode()
        return response

    if request.method != "POST":
        response.status_code = 405
        response.body = b"Method not allowed"
        return response

    try:
        body = json.loads(request.body)
        logger.info(f"Received update: {body.get('update_id', 'unknown')}")

        # Run the async handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_process_update(body))
        finally:
            loop.close()

        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"ok": True}).encode()

    except Exception as e:
        logger.exception(f"Error processing update: {e}")
        response.status_code = 200  # Always return 200 to Telegram
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"ok": True, "error": str(e)}).encode()

    return response
