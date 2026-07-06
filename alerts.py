import os
import requests
from dotenv import load_dotenv

load_dotenv()

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def send_discord_alert(deal: dict) -> None:
    """Send a manual-review deal alert to Discord."""
    if not WEBHOOK:
        return

    content = (
        "🚨 **NCV One Piece Deal Found**\n"
        f"**{deal['title']}**\n"
        f"Source: {deal['source']}\n"
        f"Total Cost: ${deal['total_cost']:.2f}\n"
        f"Target Resale: ${deal['target_resale_price']:.2f}\n"
        f"Estimated Profit: ${deal['estimated_profit']:.2f}\n"
        f"Link: {deal['url']}\n\n"
        "Manual checkout only. Verify condition/photos before buying."
    )
    requests.post(WEBHOOK, json={"content": content}, timeout=10)
