import os
import requests
from dotenv import load_dotenv

load_dotenv()

EBAY_TOKEN = os.getenv("EBAY_ACCESS_TOKEN", "").strip()
MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip() or "EBAY_US"


def search_ebay(keyword: str, limit: int = 10) -> list[dict]:
    """Search active eBay fixed-price/auction listings via official Browse API.

    Requires EBAY_ACCESS_TOKEN in .env.
    Returns an empty list if no token is configured.
    """
    if not EBAY_TOKEN:
        return []

    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {EBAY_TOKEN}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
    }
    params = {
        "q": keyword,
        "limit": limit,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION}",
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    listings = []
    for item in data.get("itemSummaries", []):
        price = float(item.get("price", {}).get("value", 0) or 0)
        shipping = 0.0
        shipping_options = item.get("shippingOptions", [])
        if shipping_options:
            shipping = float(shipping_options[0].get("shippingCost", {}).get("value", 0) or 0)

        listings.append({
            "source": "eBay",
            "title": item.get("title", ""),
            "price": price,
            "shipping": shipping,
            "url": item.get("itemWebUrl", ""),
        })
    return listings
