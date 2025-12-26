"""
my_bot_runner.py
Runs Telegram bot polling only.
Flask/WebApp/API will be served by gunicorn (keep_alive:app)
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram import Update
from telegram.error import NetworkError

# ✅ Handlers
from handlers.start import start
from handlers.problems import problems_cmd, problems_pagination_callback
from handlers.register import register_cmd
from handlers.submit import submit_cmd, handle_code, judge_worker
from handlers.history import history_cmd, history_pagination_callback
from handlers.rating import rating_cmd
from handlers.profile import profile_cmd
from handlers.rankings import rankings_cmd, rankings_pagination_callback
from handlers.problem_details import problem_details_cmd

# ✅ Env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ✅ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(context.error, NetworkError):
        if isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text("⚠️ Network issues detected. Please try again later.")
            except Exception as e:
                logger.error(f"Failed to send network error message: {e}")


async def start_workers(app):
    for _ in range(3):
        asyncio.create_task(judge_worker())
    print("🚀 Judge workers started!")


def build_app():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(start_workers)
        .build()
    )

    # ✅ Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_cmd))
    app.add_handler(CommandHandler("problems", problems_cmd))
    app.add_handler(CommandHandler("problem_details", problem_details_cmd))
    app.add_handler(CommandHandler("submit", submit_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("rating", rating_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("rankings", rankings_cmd))

    # ✅ Pagination callbacks
    app.add_handler(CallbackQueryHandler(problems_pagination_callback, pattern=r"^problems_page_\d+$"))
    app.add_handler(CallbackQueryHandler(history_pagination_callback, pattern=r"^history_page_\d+$"))
    app.add_handler(CallbackQueryHandler(rankings_pagination_callback, pattern=r"^rankings_page_\d+$"))

    # ✅ Code input handler
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_code))

    # ✅ Errors
    app.add_error_handler(error_handler)

    return app


async def _run_bot_async():
    """
    Proper async init + webhook delete + polling
    """
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing. Set it in Render Environment Variables.")
        return

    app = build_app()

    print("🤖 Bot starting (polling)...")

    # ✅ Proper initialize
    await app.initialize()

    # ✅ Disable webhook (async)
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook removed (polling mode)")
    except Exception as e:
        print("⚠️ Webhook remove failed:", e)

    # ✅ Start application
    await app.start()
    await app.updater.start_polling()

    print("✅ Bot is running!")

    # ✅ Keep running forever
    await asyncio.Event().wait()


def run_bot():
    """
    Called from keep_alive.py inside a background thread
    """
    try:
        asyncio.run(_run_bot_async())
    except Exception as e:
        print("❌ Bot crashed:", e)
