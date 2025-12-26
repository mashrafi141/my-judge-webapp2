# handlers/register.py

from telegram import Update
from telegram.ext import ContextTypes
from utils.io_utils import safe_reply
import user_utils

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if user_utils.is_user_registered(user_id):
        await safe_reply(update, "✅ You are already registered.")
        return

    if len(args) != 2:
        await safe_reply(update, "❗ Usage: /register <username> <gmail>")
        return

    username, email = args

    if not email.endswith("@gmail.com"):
        await safe_reply(update, "❗ Email must be a valid Gmail address.")
        return

    success, message = user_utils.register_user(user_id, username, email)
    await safe_reply(update, message)
