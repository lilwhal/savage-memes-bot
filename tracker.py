"""
Tracker - keeps a log of posted 9gag post IDs to avoid duplicates.
Stored in posted_log.json which is committed back to the repo by the workflow.
"""
import json
import os
from datetime import datetime

LOG_FILE = "posted_log.json"


def load_log() -> dict:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return {"posted_ids": [], "history": []}


def save_log(log: dict):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def already_posted(post_id: str) -> bool:
    log = load_log()
    return post_id in log["posted_ids"]


def mark_posted(post_id: str, platform: str, title: str):
    log = load_log()
    if post_id not in log["posted_ids"]:
        log["posted_ids"].append(post_id)
    log["history"].append({
        "id": post_id,
        "title": title,
        "platform": platform,
        "posted_at": datetime.utcnow().isoformat(),
    })
    # Keep history to last 500 entries
    log["history"] = log["history"][-500:]
    save_log(log)


def filter_unposted(posts: list[dict]) -> list[dict]:
    """Return only posts that haven't been posted yet."""
    return [p for p in posts if not already_posted(p["id"])]
