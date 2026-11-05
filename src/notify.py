import os

import requests


def send_discord(message: str) -> None:
    """Post a text message to a Discord channel through a webhook."""
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set")
    response = requests.post(url, json={"content": message[:2000]}, timeout=15)
    response.raise_for_status()