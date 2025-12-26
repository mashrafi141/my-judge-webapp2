from pymongo import MongoClient
from datetime import datetime
from pytz import timezone
import os
from dotenv import load_dotenv

# Current BD Time
def get_bd_time():
    return datetime.now(timezone('Asia/Dhaka')).strftime("%Y-%m-%d %H:%M:%S")

# 🔹 Load .env file
load_dotenv()

# 🔹 Get Mongo URI from .env
MONGO_URI = os.getenv("MONGO_URI")

# 🔹 Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client.codejudge         # Database name
users_col = db.users          # Collection name

LEVEL_RATING = {
    "Easy": 5,
    "Medium": 10,
    "Medium++": 15,
    "Hard": 20
}

# ---------------- Registration Utilities ----------------

def is_user_registered(user_id: int):
    user_id = str(user_id)
    user = users_col.find_one({"_id": user_id})
    return user is not None and "username" in user and "gmail" in user

def register_user(user_id: int, username: str, gmail: str):
    user_id = str(user_id)

    if users_col.find_one({"username": username}):
        return False, "❌ Username is already taken. Please try another."

    if users_col.find_one({"_id": user_id}):
        return False, "❌ You have already registered."

    users_col.insert_one({
        "_id": user_id,
        "username": username,
        "gmail": gmail,
        "registered_at": get_bd_time(),
        "rating": 0,
        "submission_count": 0,
        "total_rating": 0,
        "submissions": [],
        "accepted_problems": [],
        "wrong_problems": []
    })
    return True, "✅ Registration successful!"

# ---------------- Core Utilities ----------------

def ensure_user_initialized(user_id: int):
    user_id = str(user_id)
    user = users_col.find_one({"_id": user_id})
    if not user:
        users_col.insert_one({
            "_id": user_id,
            "rating": 0,
            "submission_count": 0,
            "total_rating": 0,
            "submissions": [],
            "accepted_problems": [],
            "wrong_problems": []
        })

def update_user_rating(user_id: int, level: str, problem_id: int, submission=None, verdict=None):
    user_id = str(user_id)
    ensure_user_initialized(user_id)
    points = LEVEL_RATING.get(level, 0)

    user = users_col.find_one({"_id": user_id})
    if not user:
        return

    update_doc = {"$inc": {"submission_count": 1}}

    already_accepted = problem_id in user.get("accepted_problems", [])
    already_wrong = problem_id in user.get("wrong_problems", [])

    if verdict == "✅ Accepted":
        if not already_accepted:
            update_doc["$inc"]["rating"] = points
            update_doc["$inc"]["total_rating"] = points
            update_doc.setdefault("$push", {})["accepted_problems"] = problem_id
    else:
        if not already_accepted and not already_wrong:
            update_doc.setdefault("$push", {})["wrong_problems"] = problem_id

    if submission:
        update_doc.setdefault("$push", {})["submissions"] = submission

    users_col.update_one({"_id": user_id}, update_doc)

def get_user_rating(user_id: int):
    user_id = str(user_id)
    ensure_user_initialized(user_id)
    user = users_col.find_one({"_id": user_id})
    if not user:
        return 0, 0
    submission_count = user.get("submission_count", 0)
    total_rating = user.get("total_rating", 0)
    rating = user.get("rating", 0)
    avg = round(total_rating / submission_count, 2) if submission_count > 0 else 0
    return rating, avg

def get_user_submissions(user_id: int):
    user_id = str(user_id)
    ensure_user_initialized(user_id)
    user = users_col.find_one({"_id": user_id})
    if not user:
        return []
    return user.get("submissions", [])

def save_submission(user_id: int, submission: dict):
    user_id = str(user_id)
    ensure_user_initialized(user_id)
    users_col.update_one(
        {"_id": user_id},
        {"$push": {"submissions": submission}}
    )

def get_user_profile(user_id: int):
    user_id = str(user_id)
    user = users_col.find_one({"_id": user_id})
    return user
