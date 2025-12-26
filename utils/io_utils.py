from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError

async def safe_reply(update: Update, text: str, parse_mode=None, **kwargs):
    """
    Safely sends a reply to the user.
    Catches and logs Telegram network errors.
    Supports additional arguments like reply_markup.
    """
    try:
        await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except NetworkError as e:
        print(f"⚠️ Telegram NetworkError: {e}")
    except Exception as e:
        print(f"❗ Unexpected error during reply: {e}")
