# handlers/history.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from utils.io_utils import safe_reply
import user_utils

ITEMS_PER_PAGE = 10

def build_history_message(user_id, page):
    submissions = user_utils.get_user_submissions(user_id)
    total_subs = len(submissions)
    total_pages = (total_subs + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if page < 1 or page > total_pages:
        return f"❗ Page {page} does not exist. Total pages: {total_pages}", None

    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_subs)
    message = f"📜 Submission History (Page {page}/{total_pages}):\n\n"

    for i, sub in enumerate(submissions[start_idx:end_idx], start=start_idx+1):
        verdict = sub.get("verdict", "N/A").strip()
        problem_id = str(sub.get("problem_id", "N/A"))
        problem_name = sub.get("problem_name", "N/A")
        lang = sub.get("lang", "N/A")
        message += f"{i}. [{problem_id}] {problem_name} [{lang}] — {verdict}\n"

    keyboard = []
    if total_pages > 1:
        buttons = []
        if page > 1:
            buttons.append(InlineKeyboardButton("⏮ First", callback_data="history_page_1"))
            buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"history_page_{page-1}"))
        if page < total_pages:
            buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"history_page_{page+1}"))
            buttons.append(InlineKeyboardButton("Last ⏭", callback_data=f"history_page_{total_pages}"))
        keyboard.append(buttons)

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    return message, reply_markup

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_utils.is_user_registered(user_id):
        await safe_reply(update, "❗ You are not registered yet. Use /register <username> <gmail> to register.")
        return

    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])

    msg, reply_markup = build_history_message(user_id, page)
    await safe_reply(update, msg, reply_markup=reply_markup)

# ✅ Callback handler for buttons
async def history_pagination_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    if not user_utils.is_user_registered(user_id):
        await query.answer("❗ You are not registered.")
        return

    data = query.data
    if not data.startswith("history_page_"):
        await query.answer()
        return

    page = int(data.split("_")[-1])
    msg, reply_markup = build_history_message(user_id, page)
    await query.edit_message_text(text=msg, reply_markup=reply_markup)
    await query.answer()
