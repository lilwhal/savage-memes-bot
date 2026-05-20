"""
refresh_token.py - Automatically refreshes Meta long-lived token
and updates the GitHub Secret so the bot never stops working.
"""
import os
import requests
import json
import base64
from datetime import datetime

def refresh_meta_token():
    token = os.environ.get("META_ACCESS_TOKEN")
    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")

    print("[Refresh] Exchanging for long-lived token...")
    resp = requests.get(
        "https://graph.facebook.com/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        }
    )
    data = resp.json()
    new_token = data.get("access_token")
    if not new_token:
        print(f"[Refresh] Failed to refresh token: {data}")
        return False

    print("[Refresh] Got new long-lived token, updating GitHub Secret...")
    update_github_secret("META_ACCESS_TOKEN", new_token)
    return True


def update_github_secret(secret_name: str, secret_value: str):
    gh_token = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")

    # Get repo public key for encryption
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github+json"}
    )
    key_data = key_resp.json()
    public_key = key_data["key"]
    key_id = key_data["key_id"]

    # Encrypt secret using PyNaCl
    from nacl import encoding, public
    pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = base64.b64encode(box.encrypt(secret_value.encode("utf-8"))).decode("utf-8")

    # Update secret
    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted, "key_id": key_id}
    )
    if put_resp.status_code in [201, 204]:
        print(f"[Refresh] GitHub Secret '{secret_name}' updated successfully!")
    else:
        print(f"[Refresh] Failed to update secret: {put_resp.text}")


if __name__ == "__main__":
    refresh_meta_token()
