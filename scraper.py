"""
9gag scraper - fetches top posts from configured sections
"""
import requests
import json
import os
import time
import yt_dlp
from pathlib import Path

SECTION_TAGS = {
    "funny": "funny",
    "wtf": "wtf",
    "cute": "cute",
    "gaming": "gaming",
    "anime": "anime",
    "meme": "meme",
    "awesome": "awesome",
    "food": "food",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://9gag.com/",
}


def fetch_posts(section: str, count: int = 20) -> list[dict]:
    """Fetch top posts from a 9gag section via their internal API."""
    tag = SECTION_TAGS.get(section.lower(), section.lower())
    url = f"https://9gag.com/v1/group-posts/group/{tag}/type/hot"
    
    posts = []
    after = None
    
    while len(posts) < count:
        params = {"itemCount": 10, "entryTypes": "animated,photo,video,article"}
        if after:
            params["after"] = after

        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Scraper] Error fetching {section}: {e}")
            break

        items = data.get("data", {}).get("posts", [])
        if not items:
            break

        for item in items:
            posts.append({
                "id": item.get("id"),
                "title": item.get("title", ""),
                "tags": [t.get("key", "") for t in item.get("tags", [])],
                "upvotes": item.get("upVoteCount", 0),
                "section": section,
                "type": item.get("type"),  # Photo or Animated
                "images": item.get("images", {}),
                "url": f"https://9gag.com/gag/{item.get('id')}",
            })

        after = data.get("data", {}).get("nextCursor")
        if not after:
            break
        time.sleep(1)

    # Sort by upvotes descending
    posts.sort(key=lambda x: x["upvotes"], reverse=True)
    return posts[:count]


def download_post(post: dict, download_dir: str) -> str | None:
    """Download image or video for a post. Returns local file path or None."""
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    post_id = post["id"]
    images = post.get("images", {})

    # Try video first (Animated = GIF/video)
    if post["type"] == "Animated":
        video_url = (
            images.get("image460sv", {}).get("url")
            or images.get("image460", {}).get("url")
        )
        if video_url and video_url.endswith(".mp4"):
            dest = os.path.join(download_dir, f"{post_id}.mp4")
            try:
                r = requests.get(video_url, headers=HEADERS, timeout=30, stream=True)
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[Scraper] Downloaded video: {post_id}")
                return dest
            except Exception as e:
                print(f"[Scraper] Video download failed {post_id}: {e}")

    # Fallback to image
    img_url = (
        images.get("image700", {}).get("url")
        or images.get("image460", {}).get("url")
    )
    if img_url:
        ext = img_url.split(".")[-1].split("?")[0]
        dest = os.path.join(download_dir, f"{post_id}.{ext}")
        try:
            r = requests.get(img_url, headers=HEADERS, timeout=30, stream=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[Scraper] Downloaded image: {post_id}")
            return dest
        except Exception as e:
            print(f"[Scraper] Image download failed {post_id}: {e}")

    return None
