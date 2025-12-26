# handlers/rankings.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from utils.io_utils import safe_reply
import user_utils
from datetime import datetime

ITEMS_PER_PAGE = 10

def parse_time(t_str):
    try:
        return datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
    except:
        return datetime.max

def get_sorted_users():
    users = list(user_utils.users_col.find())
    sorted_users = sorted(
        users,
        key=lambda u: (
            -u.get("rating", 0),
            len(u.get("wrong_problems", [])),
            parse_time(u.get("registered_at", "9999-12-31 23:59:59"))
        )
    )
    return sorted_users

def build_ranking_message(page):
    users = get_sorted_users()
    total_users = len(users)
    total_pages = (total_users + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if page < 1 or page > total_pages:
        return f"❗ Page {page} is invalid.", None

    msg = f"🏆 *Ranking Table (Page {page}/{total_pages}):*\n\n"
    prev_key = None
    actual_pos = 0
    rank = 0

    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_users)

    for i in range(start_idx, end_idx):
        user = users[i]
        actual_pos += 1
        cur_key = (
            user.get("rating", 0),
            len(user.get("wrong_problems", [])),
            user.get("registered_at", "9999-12-31 23:59:59")
        )

        if cur_key != prev_key:
            rank = actual_pos
            prev_key = cur_key

        username = user.get("username", "N/A")
        rating = user.get("rating", 0)
        wrong_count = len(user.get("wrong_problems", []))
        msg += f"{rank}. `{username}` — ⭐ {rating} pts, ❌ {wrong_count} WA\n"

    # Pagination buttons
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⏮ First", callback_data="rankings_page_1"))
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"rankings_page_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"rankings_page_{page+1}"))
        buttons.append(InlineKeyboardButton("Last ⏭", callback_data=f"rankings_page_{total_pages}"))

    keyboard = [buttons] if buttons else []
    return msg, InlineKeyboardMarkup(keyboard) if keyboard else None

# ✅ /rankings command
async def rankings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, reply_markup = build_ranking_message(page=1)
    await safe_reply(update, msg, parse_mode="Markdown", reply_markup=reply_markup)

# ✅ Callback handler
async def rankings_pagination_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if not data.startswith("rankings_page_"):
        await query.answer()
        return

    try:
        page = int(data.split("_")[-1])
    except:
        await query.answer("Invalid page.")
        return

    msg, reply_markup = build_ranking_message(page)
    await query.edit_message_text(text=msg, parse_mode="Markdown", reply_markup=reply_markup)
    await query.answer()
