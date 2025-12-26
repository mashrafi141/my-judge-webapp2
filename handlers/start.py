import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from utils.io_utils import safe_reply


def build_webapp_url(base_url: str, user_id: int) -> str:
    """
    Ensures WEBAPP_URL always contains user_id query param.
    Handles:
      - https://site.onrender.com/webapp
      - https://site.onrender.com/webapp?foo=1
      - https://site.onrender.com/webapp?user_id=already
    """
    if not base_url:
        return ""

    parsed = urlparse(base_url)
    q = parse_qs(parsed.query)

    # ✅ Always set user_id
    q["user_id"] = [str(user_id)]

    new_query = urlencode(q, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    webapp_url = os.getenv("WEBAPP_URL", "").strip()

    user_id = None
    if update.effective_user:
        user_id = update.effective_user.id

    keyboard = None

    # ✅ Build final URL with user_id
    final_url = build_webapp_url(webapp_url, user_id) if (webapp_url and user_id) else webapp_url

    if final_url:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open MyJudge WebApp", web_app=WebAppInfo(url=final_url))]
        ])

    text = (
        "👋 <b>Welcome to MyJudge Bot!</b>\n\n"
        "✅ <b>Open the WebApp:</b>\n"
        "Tap the button below to launch the IDE + Problems.\n\n"
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

    # ✅ If WEBAPP_URL missing, give warning message
    if not final_url:
        text += "\n\n⚠️ <b>WEBAPP_URL is not configured!</b>\nPlease set it in Render Environment Variables."

    await safe_reply(update, text, parse_mode="HTML", reply_markup=keyboard)
