import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from utils.io_utils import safe_reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = os.getenv("WEBAPP_URL", "")
    keyboard = None
    if webapp_url:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open MyJudge WebApp", web_app=WebAppInfo(url=webapp_url))]
        ])

    text = (
        "👋 <b>Welcome to MyJudge Bot!</b>\n\n"
        "📜 <b>Register first to begin:</b>\n"
        "/register <code>&lt;username&gt; &lt;gmail&gt;</code>\n"
        "<i>Example:</i> /register <code>username example@gmail.com</code>\n\n"
        "📚 <b>Available Commands:</b>\n"
        "• 🧩 /problems — List all problems\n"
        "• 🔍 /problem_details <code>&lt;problem_id&gt;</code> — View problem details\n"
        "• 💻 /submit <code>&lt;problem_id&gt; &lt;lang&gt;</code> — Submit a solution\n"
        "• 🌟 /rating — View your rating\n"
        "• 👤 /profile — View your profile\n"
        "• 📜 /history — View your accepted problems\n"
        "• 🏆 /rankings — View the leaderboard\n"
    )
    await safe_reply(update, text, parse_mode="HTML", reply_markup=keyboard)
