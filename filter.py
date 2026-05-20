"""
Content filter - screens posts for hate speech, racism, and blacklisted content.
"""
import json
import re

# Core hate speech / racism keyword list
HATE_KEYWORDS = [
    # Racial slurs (common ones - expand as needed)
    "nigger", "nigga", "chink", "spic", "kike", "gook", "wetback", "towelhead",
    "raghead", "zipperhead", "coon", "darkie", "paki", "beaner", "cracker",
    "honky", "tranny", "retard", "faggot", "dyke",
    # Nazi / white supremacy
    "heil hitler", "white power", "white supremacy", "kkk", "ku klux",
    "nazi", "sieg heil", "aryan", "14 words", "88",
    # General hate
    "kill all", "death to", "genocide",
]

# Compile regex for fast matching (whole word where possible)
_HATE_PATTERN = re.compile(
    "|".join(r"\b" + re.escape(kw) + r"\b" for kw in HATE_KEYWORDS),
    re.IGNORECASE,
)


def load_custom_blacklist(config: dict) -> list[str]:
    return config.get("blacklist_keywords", [])


def _check_text(text: str, custom: list[str]) -> tuple[bool, str]:
    """Returns (is_clean, reason)."""
    if not text:
        return True, ""

    # Check built-in hate keywords
    match = _HATE_PATTERN.search(text)
    if match:
        return False, f"Hate speech detected: '{match.group()}'"

    # Check custom blacklist
    for kw in custom:
        if kw.lower() in text.lower():
            return False, f"Blacklisted keyword: '{kw}'"

    return True, ""


def is_post_safe(post: dict, config: dict) -> tuple[bool, str]:
    """
    Returns (safe: bool, reason: str).
    Checks title and tags against hate speech + custom blacklist.
    """
    custom = load_custom_blacklist(config)

    # Check title
    clean, reason = _check_text(post.get("title", ""), custom)
    if not clean:
        return False, f"Title flagged — {reason}"

    # Check tags
    tags_text = " ".join(post.get("tags", []))
    clean, reason = _check_text(tags_text, custom)
    if not clean:
        return False, f"Tags flagged — {reason}"

    return True, ""


def filter_posts(posts: list[dict], config: dict) -> list[dict]:
    """Filter a list of posts, returning only safe ones."""
    safe = []
    for post in posts:
        ok, reason = is_post_safe(post, config)
        if ok:
            safe.append(post)
        else:
            print(f"[Filter] Skipping post {post['id']} — {reason}")
    return safe
