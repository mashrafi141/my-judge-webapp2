import json
import os

PROBLEM_FOLDER = "problems"

def get_problem_file_by_id(pid):
    """
    Return the filename where the problem with the given ID should be located.
    E.g., ID 37 -> problems_21_40.json
    """
    start = ((pid - 1) // 20) * 20 + 1
    end = start + 19
    return os.path.join(PROBLEM_FOLDER, f"problems_{start}_{end}.json")

def find_problem_by_id(pid):
    """
    Returns a problem dict given a numeric ID.
    """
    filename = get_problem_file_by_id(pid)
    try:
        with open(filename, "r") as f:
            problems = json.load(f)
            for p in problems:
                if p["id"] == pid:
                    return p
    except FileNotFoundError:
        print(f"[Error] Problem file not found: {filename}")
    return None

def list_grouped_problems():
    """
    Returns a nested dict of {category -> level -> list of problems}
    Useful for generating the problem list view.
    """
    from collections import defaultdict

    grouped = defaultdict(lambda: defaultdict(list))

    # Load all problem files in the folder
    for file in os.listdir(PROBLEM_FOLDER):
        if file.startswith("problems_") and file.endswith(".json"):
            filepath = os.path.join(PROBLEM_FOLDER, file)
            try:
                with open(filepath, "r") as f:
                    problems = json.load(f)
                    for p in problems:
                        cat = p.get("category", "Uncategorized")
                        lvl = p.get("level", "Unknown")
                        grouped[cat][lvl].append(p)
            except:
                continue

    return grouped



def load_all_problems():
    """Load all problems from all problems_*.json files and return a flat list."""
    all_problems = []
    if not os.path.exists(PROBLEM_FOLDER):
        return all_problems
    for file in os.listdir(PROBLEM_FOLDER):
        if file.startswith("problems_") and file.endswith(".json"):
            filepath = os.path.join(PROBLEM_FOLDER, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    problems = json.load(f)
                    if isinstance(problems, list):
                        all_problems.extend(problems)
            except Exception as e:
                print(f"⚠️ Failed loading {filepath}: {e}")
                continue
    return all_problems
