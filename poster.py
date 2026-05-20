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
    resp = requests.get(
        f"{GRAPH_URL}/{page_id}",
        params={"fields": "access_token", "access_token": user_token}
    )
    data = resp.json()
    page_token = data.get("access_token")
    if not page_token:
        print(f"[Poster] Could not get page token, using user token.")
        return user_token
    print("[Poster] Got page token successfully")
    return page_token


def upload_to_imgbb(file_path: str) -> str | None:
    try:
        api_key = _get_env("IMGBB_API_KEY")
        with open(file_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": img_data, "expiration": 600}
        )
        resp.raise_for_status()
        url = resp.json()["data"]["url"]
        print(f"[Poster] Uploaded to imgbb: {url}")
        return url
    except Exception as e:
        print(f"[Poster] imgbb upload failed: {e}")
        return None


# ─── Instagram ────────────────────────────────────────────────────────────────

def post_to_instagram(file_path: str, caption: str) -> bool:
    try:
        user_token = _get_env("META_ACCESS_TOKEN")
        ig_id = _get_env("INSTAGRAM_ACCOUNT_ID")
        is_video = file_path.endswith(".mp4")

        if is_video:
            page_id = _get_env("FACEBOOK_PAGE_ID")
            page_token = get_page_token(user_token, page_id)

            with open(file_path, "rb") as f:
                upload = requests.post(
                    f"{GRAPH_URL}/{page_id}/videos",
                    data={"published": "false", "access_token": page_token},
                    files={"source": f}
                )
            upload.raise_for_status()
            fb_video_id = upload.json().get("id")

            video_url = None
            for _ in range(10):
                time.sleep(5)
                video_info = requests.get(
                    f"{GRAPH_URL}/{fb_video_id}",
                    params={"fields": "source", "access_token": page_token}
                ).json()
                video_url = video_info.get("source")
                if video_url:
                    break

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
            image_url = upload_to_imgbb(file_path)
            if not image_url:
                return False

            resp = requests.post(
                f"{GRAPH_URL}/{ig_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": user_token,
                }
            )

        data = resp.json()
        if resp.status_code != 200:
            print(f"[Poster] Instagram API error: {data}")
            return False

        container_id = data["id"]
        print(f"[Poster] Instagram container created: {container_id}")

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

        pub = requests.post(
            f"{GRAPH_URL}/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": user_token},
        )
        pub_data = pub.json()
        if pub.status_code != 200:
            print(f"[Poster] Instagram publish error: {pub_data}")
            return False

        print(f"[Poster] Instagram posted: {pub_data.get('id')}")
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

        data = resp.json()
        if resp.status_code != 200:
            print(f"[Poster] Facebook API error: {data}")
            return False

        print(f"[Poster] Facebook posted: {data.get('id')}")
        return True

    except Exception as e:
        print(f"[Poster] Facebook failed: {e}")
        return False


# ─── Threads ──────────────────────────────────────────────────────────────────

def post_to_threads(file_path: str, caption: str) -> bool:
    try:
        # Use dedicated Threads token
        threads_token = _get_env("THREADS_ACCESS_TOKEN")
        threads_id = _get_env("THREADS_ACCOUNT_ID")
        is_video = file_path.endswith(".mp4")

        if is_video:
            # For videos use Facebook page to get public URL
            user_token = _get_env("META_ACCESS_TOKEN")
            page_id = _get_env("FACEBOOK_PAGE_ID")
            page_token = get_page_token(user_token, page_id)

            with open(file_path, "rb") as f:
                upload = requests.post(
                    f"{GRAPH_URL}/{page_id}/videos",
                    data={"published": "false", "access_token": page_token},
                    files={"source": f}
                )
            upload.raise_for_status()
            fb_video_id = upload.json().get("id")

            video_url = None
            for _ in range(10):
                time.sleep(5)
                video_info = requests.get(
                    f"{GRAPH_URL}/{fb_video_id}",
                    params={"fields": "source", "access_token": page_token}
                ).json()
                video_url = video_info.get("source")
                if video_url:
                    break

            if not video_url:
                print("[Poster] Threads: Could not get video URL")
                return False

            resp = requests.post(
                f"{GRAPH_URL}/{threads_id}/threads",
                data={
                    "media_type": "VIDEO",
                    "video_url": video_url,
                    "text": caption,
                    "access_token": threads_token,
                }
            )
        else:
            image_url = upload_to_imgbb(file_path)
            if not image_url:
                return False

            resp = requests.post(
                f"{GRAPH_URL}/{threads_id}/threads",
                data={
                    "media_type": "IMAGE",
                    "image_url": image_url,
                    "text": caption,
                    "access_token": threads_token,
                }
            )

        data = resp.json()
        if resp.status_code != 200:
            print(f"[Poster] Threads API error: {data}")
            return False

        container_id = data["id"]
        time.sleep(5)

        pub = requests.post(
            f"{GRAPH_URL}/{threads_id}/threads_publish",
            data={"creation_id": container_id, "access_token": threads_token},
        )
        pub_data = pub.json()
        if pub.status_code != 200:
            print(f"[Poster] Threads publish error: {pub_data}")
            return False

        print(f"[Poster] Threads posted: {pub_data.get('id')}")
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
