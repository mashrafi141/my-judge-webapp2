# handlers/profile.py

from telegram import Update
from telegram.ext import ContextTypes
from utils.io_utils import safe_reply
import user_utils

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = user_utils.get_user_profile(user_id)

    if not profile:
        await safe_reply(update, "❗ You are not registered. Please register using `/register <username> <gmail>`")
        return

    username = profile.get("username", "N/A")
    gmail = profile.get("gmail", "N/A")
    reg_time = profile.get("registered_at", "N/A")
    rating = profile.get("rating", 0)
    total_sub = profile.get("submission_count", 0)
    ac_count = len(profile.get("accepted_problems", []))
    wa_count = len(profile.get("wrong_problems", []))

    users = list(user_utils.users_col.find())
    sorted_users = sorted(users, key=lambda x: (-x.get("rating", 0), len(x.get("wrong_problems", []))))
    
    rank = "-"
    for idx, u in enumerate(sorted_users, 1):
        if u["_id"] == str(user_id):
            rank = idx
            break

    msg = (
        f"👤 *Your Profile*\n"
        f"• Username: `{username}`\n"
        f"• Gmail: `{gmail}`\n"
        f"• Registered: `{reg_time}`\n"
        f"• Rating: `{rating}`\n"
        f"• Total Submissions: `{total_sub}`\n"
        f"• ✅ Accepted: `{ac_count}`\n"
        f"• ❌ Wrong: `{wa_count}`\n"
        f"• 🏅 Rank: `{rank}`"
    )
    await safe_reply(update, msg, parse_mode="Markdown")
