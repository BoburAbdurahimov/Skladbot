"""
Local runner for the Sklad bot.
Uses aiogram's built-in polling for local development/testing.

Usage:
  1. Set environment variable BOT_TOKEN:
       set BOT_TOKEN=your_bot_token_here    (Windows)
       export BOT_TOKEN=your_bot_token_here  (Linux/Mac)

  2. Run:
       python run_local.py

The bot will start polling for updates (no webhook needed for local testing).
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        print("=" * 60)
        print("  ERROR: BOT_TOKEN environment variable is not set!")
        print()
        print("  Windows:  set BOT_TOKEN=your_token_here")
        print("  Linux:    export BOT_TOKEN=your_token_here")
        print("=" * 60)
        sys.exit(1)

    from bot.main import bot, dp

    logger.info("🚀 Sklad Bot ishga tushdi (polling rejimida)")
    logger.info("   /start - botni sinash")
    logger.info("   Ctrl+C — to'xtatish")

    # Delete any existing webhook so polling works
    await bot.delete_webhook(drop_pending_updates=True)

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
