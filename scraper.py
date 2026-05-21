"""
9gag scraper - fetches top posts from configured tags
"""
import requests
import os
import time
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://9gag.com/",
}

def fetch_posts(tag: str, count: int = 50) -> list[dict]:
    url = f"https://9gag.com/v1/tag-posts/tag/{tag}/type/hot"
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
            print(f"[Scraper] Error fetching tag '{tag}': {e}")
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
                "downvotes": item.get("downVoteCount", 0),
                "comments": item.get("commentsCount", 0),
                "section": tag,
                "type": item.get("type"),
                "images": item.get("images", {}),
                "url": f"https://9gag.com/gag/{item.get('id')}",
            })

        after = data.get("data", {}).get("nextCursor")
        if not after:
            break
        time.sleep(1)

    return posts[:count]


def download_post(post: dict, download_dir: str) -> str | None:
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    post_id = post["id"]
    images = post.get("images", {})

    # Try video first (Animated OR Video type)
    if post["type"] in ("Animated", "Video"):
        video_url = (
            images.get("image460sv", {}).get("url")
            or images.get("image460svwm", {}).get("url")
            or images.get("image460", {}).get("url")
        )
        if video_url and ".mp4" in video_url:
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
