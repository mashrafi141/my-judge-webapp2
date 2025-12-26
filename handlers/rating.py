# handlers/rating.py

from telegram import Update
from telegram.ext import ContextTypes
from utils.io_utils import safe_reply
import user_utils

async def rating_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not user_utils.is_user_registered(user_id):
        await safe_reply(update, "❗ You are not registered yet. Use /register <username> <gmail> to register.")
        return

    rating, avg = user_utils.get_user_rating(user_id)

    msg = (
        f"🌟 Your rating: {rating}\n"
        f"📊 Average points per submission: {avg:.2f}"
    )

    await safe_reply(update, msg)
