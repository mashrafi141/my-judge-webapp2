import asyncio
import os
import subprocess
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from utils.io_utils import safe_reply
from utils.problem_utils import find_problem_by_id
import user_utils

pending_submissions = {}
submission_queue = asyncio.Queue()

def run_code(lang, code, input_data):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if lang == "py":
                filename = os.path.join(tmpdir, "main.py")
                with open(filename, "w") as f:
                    f.write(code)
                cmd = ["python", filename]
            elif lang == "c":
                src = os.path.join(tmpdir, "main.c")
                out = os.path.join(tmpdir, "main.out")
                with open(src, "w") as f:
                    f.write(code)
                subprocess.run(["gcc", src, "-o", out], check=True)
                cmd = [out]
            elif lang == "cpp":
                src = os.path.join(tmpdir, "main.cpp")
                out = os.path.join(tmpdir, "main.out")
                with open(src, "w") as f:
                    f.write(code)
                subprocess.run(["g++", src, "-o", out], check=True)
                cmd = [out]
            elif lang == "java":
                src = os.path.join(tmpdir, "Main.java")
                with open(src, "w") as f:
                    f.write(code)
                subprocess.run(["javac", src], check=True)
                cmd = ["java", "-cp", tmpdir, "Main"]
            else:
                return "❗ Unsupported language."

            proc = subprocess.run(
                cmd,
                input=input_data.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3
            )
            if proc.returncode != 0:
                return f"⚠️ Runtime Error:\n{proc.stderr.decode().strip()}"
            return proc.stdout.decode().strip()
    except subprocess.TimeoutExpired:
        return "⏰ Time Limit Exceeded"
    except subprocess.CalledProcessError as e:
        return f"⚠️ Compilation Error:\n{str(e)}"
    except Exception as e:
        return f"❗ Error: {str(e)}"

async def run_code_async(lang, code, input_data):
    return await asyncio.to_thread(run_code, lang, code, input_data)

def normalize_output(text):
    return [line.strip() for line in text.strip().split('\n') if line.strip()]

def compare_outputs(expected, result, allow_unordered=False):
    expected_lines = normalize_output(expected)
    result_lines = normalize_output(result)

    if allow_unordered:
        return sorted(expected_lines) == sorted(result_lines)
    else:
        return expected_lines == result_lines

async def judge_code(code, lang, problem, allow_unordered_output=False):
    for tc in problem["test_cases"]:
        result = await run_code_async(lang, code, tc["input"])

        if result.startswith(("⚠️", "⏰", "❗")):
            return result

        if not compare_outputs(tc["output"], result, allow_unordered_output):
            expected_clean = '\n'.join(normalize_output(tc["output"]))
            result_clean = '\n'.join(normalize_output(result))
            return (
                "❌ Wrong Answer\n"
                f"\nTest case input:\n{tc['input']}\n\n"
                f"Expected output:\n{expected_clean}\n\n"
                f"Your output:\n{result_clean}"
            )

    return "✅ Accepted"

async def submit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_utils.is_user_registered(user_id):
        await safe_reply(update, "❗ You are not registered yet. Use /register <username> <gmail> to register.")
        return

    args = context.args
    if len(args) != 2:
        msg = "❗ Usage: /submit <problem_id> <lang>\nExample: `/submit 1 cpp`"
        await safe_reply(update, escape_markdown(msg, version=2), parse_mode="MarkdownV2")
        return

    pid, lang = args
    if not pid.isdigit() or lang not in ["py", "c", "cpp", "java"]:
        msg = "❗ Invalid format. ID must be a number. Language must be one of `py`, `c`, `cpp`, `java`."
        await safe_reply(update, escape_markdown(msg, version=2), parse_mode="MarkdownV2")
        return

    pid = int(pid)
    prob = find_problem_by_id(pid)
    if not prob:
        await safe_reply(update, f"❗ Problem ID {pid} not found.")
        return

    pending_submissions[user_id] = {"pid": pid, "lang": lang}

    msg = "📥 Now send your code in the *next message* (as plain text or multiline)."
    await safe_reply(update, escape_markdown(msg, version=2), parse_mode="MarkdownV2")

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_submissions:
        return

    code = update.message.text
    submission_data = pending_submissions.pop(user_id)
    pid = submission_data["pid"]
    lang = submission_data["lang"]
    prob = find_problem_by_id(pid)

    await safe_reply(update, "📥 Code received! ✅\n⏳...wait for the result...⏳")

    await submission_queue.put({
        "update": update,
        "user_id": user_id,
        "code": code,
        "lang": lang,
        "pid": pid,
        "problem": prob
    })

async def process_submission(update, user_id, code, lang, pid, prob):
    verdict = await judge_code(code, lang, prob)

    user_utils.ensure_user_initialized(user_id)
    submission_record = {
        "problem_id": pid,
        "problem_name": prob.get("name", "Unknown Problem"),
        "verdict": verdict,
        "lang": lang
    }

    user_utils.save_submission(user_id, submission_record)
    user_utils.update_user_rating(user_id, prob.get("level", "Easy"), pid, submission=submission_record, verdict=verdict)

    await safe_reply(update, f"📝 Submission result:\n{verdict}")

async def judge_worker():
    while True:
        submission = await submission_queue.get()
        try:
            await process_submission(
                submission["update"],
                submission["user_id"],
                submission["code"],
                submission["lang"],
                submission["pid"],
                submission["problem"]
            )
        except Exception as e:
            print(f"❗️ Error while judging: {e}")
        submission_queue.task_done()
