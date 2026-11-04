import os

import requests


def send_discord(message: str) -> None:
    """Post a message to the Discord channel behind the webhook."""
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set")
    response = requests.post(url, json={"content": message[:1900]}, timeout=15)
    response.raise_for_status()
