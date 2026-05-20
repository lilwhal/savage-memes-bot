"""
reels.py - Savage Memes Bot Reels poster
Picks top video posts and publishes them as Reels to Facebook (and Instagram when approved).
"""
import json
import os
import sys
import time
from scraper import fetch_posts, download_post
from filter import filter_posts
from poster import get_page_token, upload_video_chunked
import requests

CONFIG_FILE = "config.json"
REELS_LOG_FILE = "reels_log.json"
DOWNLOAD_DIR = "tmp_media"
GRAPH_URL = "https://graph.facebook.com/v19.0"


def load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def load_reels_log() -> dict:
    if os.path.exists(REELS_LOG_FILE):
        with open(REELS_LOG_FILE, "r") as f:
            return json.load(f)
    return {"posted_ids": [], "history": []}


def save_reels_log(log: dict):
    with open(REELS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def already_posted_as_reel(post_id: str) -> bool:
    log = load_reels_log()
    return post_id in log["posted_ids"]


def mark_reel_posted(post_id: str, title: str):
    from datetime import datetime
    log = load_reels_log()
    if post_id not in log["posted_ids"]:
        log["posted_ids"].append(post_id)
    log["history"].append({
        "id": post_id,
        "title": title,
        "posted_at": datetime.utcnow().isoformat(),
    })
    log["history"] = log["history"][-500:]
    save_reels_log(log)


def cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            print(f"[Cleanup] Deleted {path}")
    except Exception as e:
        print(f"[Cleanup] Failed to delete {path}: {e}")


def post_facebook_reel(file_path: str, caption: str) -> bool:
    try:
        user_token = os.environ.get("META_ACCESS_TOKEN", "")
        page_id = os.environ.get("FACEBOOK_PAGE_ID", "")
        page_token = get_page_token(user_token, page_id)
        file_size = os.path.getsize(file_path)

        print(f"[Reels] Uploading Facebook Reel ({file_size / 1024 / 1024:.1f}MB)...")

        # Step 1: Start upload session for Reels
        start_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{page_id}/video_reels",
            data={
                "upload_phase": "start",
                "access_token": page_token,
            }
        )
        start_data = start_resp.json()
        if "video_id" not in start_data:
            print(f"[Reels] Failed to start reel upload: {start_data}")
            return False

        video_id = start_data["video_id"]
        upload_url = start_data.get("upload_url")
        print(f"[Reels] Reel upload session started: {video_id}")

        # Step 2: Upload video bytes
        with open(file_path, "rb") as f:
            upload_resp = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {page_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f
            )

        if upload_resp.status_code not in [200, 204]:
            print(f"[Reels] Upload failed: {upload_resp.text}")
            return False

        print(f"[Reels] Video uploaded successfully")

        # Step 3: Publish the Reel
        publish_resp = requests.post(
            f"https://graph.facebook.com/v19.0/{page_id}/video_reels",
            data={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": caption,
                "access_token": page_token,
            }
        )
        pub_data = publish_resp.json()
        if publish_resp.status_code != 200:
            print(f"[Reels] Publish failed: {pub_data}")
            return False

        print(f"[Reels] Facebook Reel posted: {video_id}")
        return True

    except Exception as e:
        print(f"[Reels] Facebook Reel failed: {e}")
        return False


def run():
    print("🎬 Savage Memes Reels Bot starting...")
    config = load_config()

    if not config.get("bot_enabled", True):
        print("[Reels] Bot is disabled. Exiting.")
        sys.exit(0)

    sections = config.get("sections", ["funny"])
    min_upvotes = config.get("min_upvotes", 2000)

    # Fetch posts from all sections
    all_posts = []
    for section in sections:
        print(f"[Reels] Fetching section: {section}")
        posts = fetch_posts(section, count=30)
        all_posts.extend(posts)
        time.sleep(2)

    # Deduplicate
    seen = set()
    all_posts = [p for p in all_posts if not (p["id"] in seen or seen.add(p["id"]))]

    # Videos only
    video_posts = [p for p in all_posts if p["type"] == "Animated"]
    print(f"[Reels] {len(video_posts)} video posts found")

    # Filter content
    safe_posts = filter_posts(video_posts, config)

    # Remove already posted as reels
    new_posts = [p for p in safe_posts if not already_posted_as_reel(p["id"])]

    # Filter by upvotes
    new_posts = [p for p in new_posts if p["upvotes"] >= min_upvotes]
    new_posts.sort(key=lambda x: x["upvotes"], reverse=True)

    print(f"[Reels] {len(new_posts)} new videos available above {min_upvotes} upvotes")

    if not new_posts:
        print("[Reels] No new videos to post as Reels. Exiting.")
        sys.exit(0)

    post = new_posts[0]
    print(f"\n[Reels] Processing: {post['title'][:60]} (👍 {post['upvotes']})")

    file_path = download_post(post, DOWNLOAD_DIR)
    if not file_path:
        print("[Reels] Download failed. Exiting.")
        sys.exit(1)

    caption = f"{post.get('title', '')}\n\n{' '.join(config.get('caption_hashtags', ['#meme', '#funny']))}"

    success = post_facebook_reel(file_path, caption)
    cleanup_file(file_path)

    if success:
        mark_reel_posted(post["id"], post.get("title", ""))
        print(f"\n✅ Reel posted successfully!")
    else:
        print(f"\n❌ Reel posting failed.")


if __name__ == "__main__":
    run()
