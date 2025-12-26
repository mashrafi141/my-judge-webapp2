# handlers/problem_details.py

from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from utils.io_utils import safe_reply
from utils.problem_utils import find_problem_by_id
import user_utils

async def problem_details_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not user_utils.is_user_registered(user_id):
        await safe_reply(update, "❗ You are not registered yet. Use /register <username> <gmail> to register.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await safe_reply(update, "❗ Usage: /problem_details <problem_id>")
        return

    pid = int(context.args[0])
    prob = find_problem_by_id(pid)

    if not prob:
        await safe_reply(update, f"🚫 Problem with ID {pid} not found.")
        return

    samples = prob['test_cases'][:2] if len(prob['test_cases']) >= 2 else prob['test_cases']

    # Escape all user visible text to avoid MarkdownV2 parsing errors
    msg = (
        f"*📘 Problem Details:*\n"
        f"*ID:* `{prob['id']}`\n"
        f"*Title:* *{escape_markdown(prob['name'], version=2)}*\n"
        f"*Type:* {escape_markdown(prob['category'], version=2)}\n"
        f"*Level:* {escape_markdown(prob['level'], version=2)}\n\n"
        f"*Description:* \n{escape_markdown(prob['description'], version=2)}\n"
    )

    for i, sample in enumerate(samples):
        input_escaped = escape_markdown(sample['input'], version=2)
        output_escaped = escape_markdown(sample['output'], version=2)

        msg += (
            f"*🧾 Sample Input {i+1}:*\n"
            f"```\n{input_escaped}\n```\n"
            f"*🖨️ Sample Output {i+1}:*\n"
            f"```\n{output_escaped}\n```\n"
        )
        
    
    msg += f"\n📤 To submit:\n`/submit {prob['id']} cpp`"
    
    await safe_reply(update, msg, parse_mode="MarkdownV2")
