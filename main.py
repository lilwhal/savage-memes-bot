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
    title = post.get("title", "")
    tags = config.get("caption_hashtags", ["#meme", "#funny", "#savagmemes"])
    hashtags = " ".join(tags)
    return f"{title}\n\n{hashtags}" if title else hashtags


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
    posts_per_run = config.get("posts_per_run", 1)
    platforms = config.get("platforms", ["instagram", "facebook", "threads"])

    print(f"[Bot] Sections: {sections} | Posts: {posts_per_run} | Platforms: {platforms}")

    # 1. Fetch posts from all configured sections
    all_posts = []
    for section in sections:
        print(f"[Bot] Fetching section: {section}")
        posts = fetch_posts(section, count=30)
        all_posts.extend(posts)
        time.sleep(2)

    # 2. Deduplicate posts that appear in multiple sections
    seen = set()
    all_posts = [p for p in all_posts if not (p["id"] in seen or seen.add(p["id"]))]
    print(f"[Bot] {len(all_posts)} unique posts after deduplication")

    # 3. Sort by type (videos first) then upvotes
    all_posts.sort(key=lambda x: (x["type"] == "Animated", x["upvotes"]), reverse=True)

    # 4. Filter hate speech / blacklisted content
    print(f"[Bot] Filtering content...")
    safe_posts = filter_posts(all_posts, config)
    print(f"[Bot] {len(safe_posts)} posts passed content filter")

    # 5. Remove already-posted
    new_posts = filter_unposted(safe_posts)

    # 6. Filter by minimum upvotes
    min_upvotes = config.get("min_upvotes", 1000)
    new_posts = [p for p in new_posts if p["upvotes"] >= min_upvotes]
    print(f"[Bot] {len(new_posts)} new posts available above {min_upvotes} upvotes")

    if not new_posts:
        print("[Bot] No new posts to share today. Exiting.")
        sys.exit(0)

    # 7. Take top N posts for this run
    to_post = new_posts[:posts_per_run]

    # 8. Download, post, cleanup
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
