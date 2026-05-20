"""
main.py - Savage Memes Bot entry point
Reads config, scrapes 9gag, filters, downloads, posts, cleans up.
"""
import json
import os
import sys
import time
from scraper import fetch_posts, download_post
from filter import filter_posts
from tracker import filter_unposted, mark_posted
from poster import publish_post

CONFIG_FILE = "config.json"
DOWNLOAD_DIR = "tmp_media"


def load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def build_caption(post: dict, config: dict) -> str:
    tags = config.get("caption_hashtags", ["#meme", "#funny", "#savagmemes"])
    return " ".join(tags)


def cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            print(f"[Cleanup] Deleted {path}")
    except Exception as e:
        print(f"[Cleanup] Failed to delete {path}: {e}")


def run():
    print("🤖 Savage Memes Bot starting...")
    config = load_config()

    if not config.get("bot_enabled", True):
        print("[Bot] Bot is disabled in config. Exiting.")
        sys.exit(0)

    sections = config.get("sections", ["funny"])
    posts_per_run = config.get("posts_per_run", 3)
    platforms = config.get("platforms", ["instagram", "facebook", "threads"])

    print(f"[Bot] Sections: {sections} | Posts: {posts_per_run} | Platforms: {platforms}")

    all_posts = []
    for section in sections:
        print(f"[Bot] Fetching section: {section}")
        posts = fetch_posts(section, count=30)
        all_posts.extend(posts)
        time.sleep(2)

    all_posts.sort(key=lambda x: x["upvotes"], reverse=True)

    print(f"[Bot] {len(all_posts)} posts fetched, filtering...")
    safe_posts = filter_posts(all_posts, config)
    print(f"[Bot] {len(safe_posts)} posts passed content filter")

    new_posts = filter_unposted(safe_posts)
    print(f"[Bot] {len(new_posts)} new posts available")

    if not new_posts:
        print("[Bot] No new posts to share today. Exiting.")
        sys.exit(0)

    to_post = new_posts[:posts_per_run]

    posted_count = 0
    for post in to_post:
        print(f"\n[Bot] Processing: {post['title'][:60]} (👍 {post['upvotes']})")

        file_path = download_post(post, DOWNLOAD_DIR)
        if not file_path:
            print(f"[Bot] Skipping {post['id']} — download failed")
            continue

        caption = build_caption(post, config)
        results = publish_post(file_path, caption, platforms)

        if any(results.values()):
            for platform, success in results.items():
                if success:
                    mark_posted(post["id"], platform, post.get("title", ""))
            posted_count += 1

        cleanup_file(file_path)

        if posted_count < len(to_post):
            time.sleep(3)

    print(f"\n✅ Done! Posted {posted_count}/{len(to_post)} posts.")


if __name__ == "__main__":
    run()
