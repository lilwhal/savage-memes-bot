"""
Poster - uploads media and publishes to Instagram, Facebook, and Threads
via the Meta Graph API.
"""
import os
import requests
import time
import base64

GRAPH_URL = "https://graph.facebook.com/v19.0"


def _get_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        raise EnvironmentError(f"Missing environment variable: {key}")
    return val


def get_page_token(user_token: str, page_id: str) -> str:
    """Exchange user token for page token."""
    resp = requests.get(
        f"{GRAPH_URL}/{page_id}",
        params={"fields": "access_token", "access_token": user_token}
    )
    data = resp.json()
    page_token = data.get("access_token")
    if not page_token:
        print(f"[Poster] Could not get page token, using user token. Response: {data}")
        return user_token
    print("[Poster] Got page token successfully")
    return page_token


def file_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ─── Instagram ────────────────────────────────────────────────────────────────

def post_to_instagram(file_path: str, caption: str) -> bool:
    try:
        user_token = _get_env("META_ACCESS_TOKEN")
        ig_id = _get_env("INSTAGRAM_ACCOUNT_ID")
        is_video = file_path.endswith(".mp4")

        # Instagram requires a public URL - upload to imgbb (free image host)
        # For videos use Facebook's video upload endpoint
        if is_video:
            # Upload video to Facebook CDN first to get public URL
            page_id = _get_env("FACEBOOK_PAGE_ID")
            page_token = get_page_token(user_token, page_id)
            
            with open(file_path, "rb") as f:
                upload = requests.post(
                    f"{GRAPH_URL}/{page_id}/videos",
                    data={
                        "published": "false",
                        "access_token": page_token
                    },
                    files={"source": f}
                )
            upload.raise_for_status()
            fb_video_id = upload.json().get("id")
            
            # Get the video URL
            video_info = requests.get(
                f"{GRAPH_URL}/{fb_video_id}",
                params={"fields": "permalink_url,source", "access_token": page_token}
            ).json()
            video_url = video_info.get("source")
            
            if not video_url:
                print("[Poster] Could not get video URL for Instagram")
                return False

            resp = requests.post(
                f"{GRAPH_URL}/{ig_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": user_token,
                }
            )
        else:
            # Upload image to imgbb for public URL
            with open(file_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            
            imgbb_resp = requests.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": "public",  # imgbb free tier
                    "image": img_data,
                    "expiration": 600  # delete after 10 mins
                }
            )
            
            if imgbb_resp.status_code != 200:
                # Fallback: try direct upload
                resp = requests.post(
                    f"{GRAPH_URL}/{ig_id}/media",
                    data={"caption": caption, "access_token": user_token},
                    files={"image": open(file_path, "rb")},
                )
            else:
                image_url = imgbb_resp.json()["data"]["url"]
                resp = requests.post(
                    f"{GRAPH_URL}/{ig_id}/media",
                    data={
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": user_token,
                    }
                )

        resp.raise_for_status()
        container_id = resp.json()["id"]
        print(f"[Poster] Instagram container created: {container_id}")

        # Wait for container to be ready
        for _ in range(15):
            status = requests.get(
                f"{GRAPH_URL}/{container_id}",
                params={"fields": "status_code,status", "access_token": user_token},
            ).json()
            sc = status.get("status_code")
            print(f"[Poster] Instagram status: {sc}")
            if sc == "FINISHED":
                break
            if sc == "ERROR":
                print(f"[Poster] Instagram container error: {status}")
                return False
            time.sleep(6)

        # Publish
        pub = requests.post(
            f"{GRAPH_URL}/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": user_token},
        )
        pub.raise_for_status()
        print(f"[Poster] Instagram posted: {pub.json().get('id')}")
        return True

    except Exception as e:
        print(f"[Poster] Instagram failed: {e}")
        return False


# ─── Facebook ─────────────────────────────────────────────────────────────────

def post_to_facebook(file_path: str, caption: str) -> bool:
    try:
        user_token = _get_env("META_ACCESS_TOKEN")
        page_id = _get_env("FACEBOOK_PAGE_ID")
        page_token = get_page_token(user_token, page_id)
        is_video = file_path.endswith(".mp4")

        if is_video:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{GRAPH_URL}/{page_id}/videos",
                    data={"description": caption, "access_token": page_token},
                    files={"source": f},
                )
        else:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{GRAPH_URL}/{page_id}/photos",
                    data={"caption": caption, "access_token": page_token},
                    files={"source": f},
                )

        resp.raise_for_status()
        print(f"[Poster] Facebook posted: {resp.json().get('id')}")
        return True

    except Exception as e:
        print(f"[Poster] Facebook failed: {e}")
        return False


# ─── Threads ──────────────────────────────────────────────────────────────────

def post_to_threads(file_path: str, caption: str) -> bool:
    try:
        user_token = _get_env("META_ACCESS_TOKEN")
        threads_id = _get_env("THREADS_ACCOUNT_ID")
        is_video = file_path.endswith(".mp4")

        media_type = "VIDEO" if is_video else "IMAGE"

        # Upload image to imgbb for public URL
        with open(file_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        imgbb_resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": "public", "image": img_data, "expiration": 600}
        )

        if imgbb_resp.status_code == 200:
            media_url = imgbb_resp.json()["data"]["url"]
        else:
            print("[Poster] Threads: Could not get public URL")
            return False

        url_key = "video_url" if is_video else "image_url"

        resp = requests.post(
            f"{GRAPH_URL}/{threads_id}/threads",
            data={
                "media_type": media_type,
                "text": caption,
                url_key: media_url,
                "access_token": user_token,
            }
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]

        time.sleep(5)

        pub = requests.post(
            f"{GRAPH_URL}/{threads_id}/threads_publish",
            data={"creation_id": container_id, "access_token": user_token},
        )
        pub.raise_for_status()
        print(f"[Poster] Threads posted: {pub.json().get('id')}")
        return True

    except Exception as e:
        print(f"[Poster] Threads failed: {e}")
        return False


# ─── Main publish function ─────────────────────────────────────────────────────

def publish_post(file_path: str, caption: str, platforms: list[str]) -> dict:
    results = {}
    for platform in platforms:
        if platform == "instagram":
            results["instagram"] = post_to_instagram(file_path, caption)
        elif platform == "facebook":
            results["facebook"] = post_to_facebook(file_path, caption)
        elif platform == "threads":
            results["threads"] = post_to_threads(file_path, caption)
    return results
