# handlers/problems.py
# handlers/problems.py
# handlers/problems.py
# handlers/problems.py

from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import user_utils
from utils.io_utils import safe_reply
from utils import problem_utils  # ✅ using the folder-based logic here

MAX_MSG_LEN = 4096
PAGE_SIZE = 10

def flatten_grouped(grouped):
    """Flatten grouped dict to a list of problems preserving order, sorted by ID."""
    flat_list = []
    for category, levels in grouped.items():
        for level, plist in levels.items():
            for p in plist:
                flat_list.append((category, level, p))

    # ✅ Sort the flat list by problem ID
    flat_list.sort(key=lambda x: x[2]["id"])
    return flat_list

def build_message(page_problems, page, total_pages):
    header = "📝 *Available Problems:*\n\n"
    lines = []
    last_cat = None
    last_lvl = None

    for cat, lvl, p in page_problems:
        if cat != last_cat:
            lines.append(f"*{cat}:*")
            last_cat = cat
            last_lvl = None
        if lvl != last_lvl:
            lines.append(f"_{lvl}_")
            last_lvl = lvl

        # ✅ Problem line with level and copyable command
        line = f"• {p['id']}. {p['name']} ({lvl})\n   `/problem_details {p['id']}`"
        lines.append(line)

    footer = (
        f"\nPage {page}/{total_pages}\n"
        "🚀 Use `/submit <problem_id> <lang>` to submit a solution.\n"
        "Supported: `py`, `c`, `cpp`, `java`\n"
        "📘 Tap on the command above (like `/problem_details 1`) to copy and get details."
    )

    return header + "\n".join(lines) + footer

def build_pagination_keyboard(page, total_pages):
    buttons = []

    if page > 1:
        buttons.append(InlineKeyboardButton("⏮ First", callback_data="problems_page_1"))
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"problems_page_{page-1}"))

    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"problems_page_{page+1}"))
        buttons.append(InlineKeyboardButton("Last ⏭", callback_data=f"problems_page_{total_pages}"))

    keyboard = [buttons] if buttons else []
    return InlineKeyboardMarkup(keyboard)

async def problems_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not user_utils.is_user_registered(user_id):
        await safe_reply(
            update,
            "❗ You are not registered yet. Use /register <username> <gmail> to register."
        )
        return

    grouped = problem_utils.list_grouped_problems()  # ✅ changed
    flat_list = flatten_grouped(grouped)

    total_pages = (len(flat_list) + PAGE_SIZE - 1) // PAGE_SIZE
    page = 1

    page_problems = flat_list[(page-1)*PAGE_SIZE : page*PAGE_SIZE]
    msg_text = build_message(page_problems, page, total_pages)
    reply_markup = build_pagination_keyboard(page, total_pages)

    await safe_reply(update, msg_text, parse_mode="Markdown", reply_markup=reply_markup)

async def problems_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not user_utils.is_user_registered(user_id):
        await query.answer("You are not registered yet. Use /register <username> <gmail>.")
        return

    data = query.data
    if not data.startswith("problems_page_"):
        await query.answer()
        return

    try:
        page = int(data.split("_")[-1])
    except:
        await query.answer()
        return

    grouped = problem_utils.list_grouped_problems()  # ✅ changed
    flat_list = flatten_grouped(grouped)
    total_pages = (len(flat_list) + PAGE_SIZE - 1) // PAGE_SIZE

    if page < 1 or page > total_pages:
        await query.answer("Invalid page.")
        return

    page_problems = flat_list[(page-1)*PAGE_SIZE : page*PAGE_SIZE]
    msg_text = build_message(page_problems, page, total_pages)
    reply_markup = build_pagination_keyboard(page, total_pages)

    await query.edit_message_text(text=msg_text, parse_mode="Markdown", reply_markup=reply_markup)
    await query.answer()
