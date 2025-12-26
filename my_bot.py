import asyncio
import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, ContextTypes
)
from telegram import Update
from telegram.error import NetworkError
import logging

# Custom keep_alive server (if using Render or Replit)
from keep_alive import keep_alive
keep_alive()  # Start Flask server

# Load handlers
from handlers.start import start
from handlers.problems import problems_cmd, problems_pagination_callback
from handlers.register import register_cmd
from handlers.submit import submit_cmd, handle_code, judge_worker
from handlers.history import history_cmd, history_pagination_callback
from handlers.rating import rating_cmd
from handlers.profile import profile_cmd
from handlers.rankings import rankings_cmd, rankings_pagination_callback
from handlers.problem_details import problem_details_cmd

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

LOCAL_MODE = os.getenv("LOCAL_MODE", "0") == "1"
# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(context.error, NetworkError):
        if isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text("⚠️ Network issues detected. Please try again later.")
            except Exception as e:
                logger.error(f"Failed to send network error message: {e}")

# ✅ Worker launcher
async def start_workers(app):
    for _ in range(3):
        asyncio.create_task(judge_worker())
    print("🚀 Judge workers started!")

# ✅ Main function
def main():
    import time
    if LOCAL_MODE:
        print("✅ LOCAL_MODE enabled: Bot polling disabled. Only WebApp/API running.")
        while True:
            time.sleep(10)

    app = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .post_init(start_workers) \
        .build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_cmd))
    app.add_handler(CommandHandler("problems", problems_cmd))
    app.add_handler(CommandHandler("problem_details", problem_details_cmd))
    app.add_handler(CommandHandler("submit", submit_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("rating", rating_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("rankings", rankings_cmd))

    # Pagination handlers
    app.add_handler(CallbackQueryHandler(problems_pagination_callback, pattern=r"^problems_page_\d+$"))
    app.add_handler(CallbackQueryHandler(history_pagination_callback, pattern=r"^history_page_\d+$"))
    app.add_handler(CallbackQueryHandler(rankings_pagination_callback, pattern=r"^rankings_page_\d+$"))

    # Code input handler
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_code))

    # Global error handler
    app.add_error_handler(error_handler)

    print("🤖 Bot started...")
    app.run_polling()

# Run the bot
if __name__ == "__main__":
    main()
