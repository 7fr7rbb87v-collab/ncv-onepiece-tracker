import os
import json
import math
import base64
import requests
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import quote

DATA_DIR = "data"
DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RETAIL_FILE = os.path.join(DATA_DIR, "retail_inventory.json")
TIKTOK_FILE = os.path.join(DATA_DIR, "tiktok_videos.json")
EBAY_STATUS_FILE = os.path.join(DATA_DIR, "ebay_status.json")

EBAY_CLIENT_ID = os.getenv("EBAY_CLIENT_ID", "").strip()
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "").strip()
EBAY_MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip() or "EBAY_US"
EBAY_RESULTS_PER_PRODUCT = int(os.getenv("EBAY_RESULTS_PER_PRODUCT", "10"))
ENABLE_EBAY = os.getenv("ENABLE_EBAY", "1").strip() == "1"


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        text = str(value).replace("$", "").replace(",", "").strip()
        if text == "" or text.lower() == "nan":
            return default
        return float(text)
    except Exception:
        return default


def clean_string(value):
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def money_targets(price):
    buy_target = round(price * 0.80, 2)
    sale_target = round(price * 1.35, 2)
    target_spread = round(sale_target - buy_target, 2)
    return buy_target, sale_target, target_spread


def get_ebay_token():
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        raise RuntimeError("Missing EBAY_CLIENT_ID or EBAY_CLIENT_SECRET GitHub secrets.")

    credentials = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    response = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def search_ebay(keyword, token):
    response = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE_ID,
        },
        params={
            "q": keyword,
            "limit": EBAY_RESULTS_PER_PRODUCT,
            "sort": "newlyListed",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("itemSummaries", [])


def parse_ebay_listing(product, listing, now):
    product_id = clean_string(product.get("product_id", ""))
    keyword = clean_string(product.get("keyword", ""))
    product_type = clean_string(product.get("type", "single"))

    title = clean_string(listing.get("title", keyword))
    price = safe_float((listing.get("price") or {}).get("value", 0))
    url = clean_string(listing.get("itemWebUrl", ""))
    image = clean_string((listing.get("image") or {}).get("imageUrl", ""))
    condition = clean_string(listing.get("condition", ""))
    item_id = clean_string(listing.get("itemId", ""))
    seller = listing.get("seller") or {}
    seller_username = clean_string(seller.get("username", ""))
    feedback_percentage = clean_string(seller.get("feedbackPercentage", ""))
    feedback_score = clean_string(seller.get("feedbackScore", ""))

    if price <= 0:
        return None

    buy_target, sale_target, target_spread = money_targets(price)

    return {
        "product_id": product_id,
        "keyword": keyword,
        "title": title,
        "price": round(price, 2),
        "buy_target": buy_target,
        "sale_target": sale_target,
        "estimated_spread": target_spread,
        "url": url,
        "image": image,
        "source": "eBay API",
        "type": product_type,
        "condition": condition,
        "seller": seller_username,
        "seller_feedback_percentage": feedback_percentage,
        "seller_feedback_score": feedback_score,
        "item_id": item_id,
        "last_checked": now,
    }


def load_csv(path, columns):
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    try:
        return pd.read_csv(path)
    except Exception as error:
        print(f"Could not read {path}: {error}")
        return pd.DataFrame(columns=columns)


def manual_deals(now):
    manual = load_csv("manual_listings.csv", ["product_id", "title", "price", "url", "image", "source", "type"])
    rows = []

    for _, item in manual.iterrows():
        price = safe_float(item.get("price", 0))
        if price <= 0:
            continue

        buy_target, sale_target, target_spread = money_targets(price)

        rows.append({
            "product_id": clean_string(item.get("product_id", "manual")),
            "keyword": clean_string(item.get("title", "")),
            "title": clean_string(item.get("title", "")),
            "price": round(price, 2),
            "buy_target": buy_target,
            "sale_target": sale_target,
            "estimated_spread": target_spread,
            "url": clean_string(item.get("url", "")),
            "image": clean_string(item.get("image", "")),
            "source": clean_string(item.get("source", "Manual")) or "Manual",
            "type": clean_string(item.get("type", "manual")) or "manual",
            "condition": "",
            "seller": "",
            "seller_feedback_percentage": "",
            "seller_feedback_score": "",
            "item_id": "",
            "last_checked": now,
        })

    return rows


def retail_inventory(now):
    retail = load_csv("retail_inventory.csv", ["product_id", "retailer", "title", "price", "url", "image", "stock_status", "store", "zip_code", "notes"])
    rows = []
    for _, item in retail.iterrows():
        price = safe_float(item.get("price", 0))
        buy_target, sale_target, target_spread = money_targets(price) if price > 0 else (0, 0, 0)
        rows.append({
            "product_id": clean_string(item.get("product_id", "")),
            "retailer": clean_string(item.get("retailer", "")),
            "title": clean_string(item.get("title", "")),
            "price": round(price, 2),
            "buy_target": buy_target,
            "sale_target": sale_target,
            "estimated_spread": target_spread,
            "url": clean_string(item.get("url", "")),
            "image": clean_string(item.get("image", "")),
            "stock_status": clean_string(item.get("stock_status", "unknown")) or "unknown",
            "store": clean_string(item.get("store", "")),
            "zip_code": clean_string(item.get("zip_code", "")),
            "notes": clean_string(item.get("notes", "")),
            "last_checked": now,
        })
    return rows


def tiktok_videos():
    videos = load_csv("tiktok_videos.csv", ["product_id", "tiktok_url", "label", "source"])
    rows = []
    for _, item in videos.iterrows():
        url = clean_string(item.get("tiktok_url", ""))
        if not url:
            continue
        rows.append({
            "product_id": clean_string(item.get("product_id", "")),
            "url": url,
            "label": clean_string(item.get("label", "TikTok Video")),
            "source": clean_string(item.get("source", "TikTok Manual")) or "TikTok Manual",
        })
    return rows


def update_history(deals, now):
    history = load_json(HISTORY_FILE, [])
    grouped = {}
    for deal in deals:
        product_id = deal.get("product_id", "")
        price = safe_float(deal.get("price", 0))
        if not product_id or price <= 0:
            continue
        grouped.setdefault(product_id, []).append(deal)

    for product_id, product_deals in grouped.items():
        prices = [safe_float(item.get("price", 0)) for item in product_deals if safe_float(item.get("price", 0)) > 0]
        if not prices:
            continue
        history.append({
            "product_id": product_id,
            "keyword": clean_string(product_deals[0].get("keyword", product_deals[0].get("title", product_id))),
            "timestamp": now,
            "lowest_price": round(min(prices), 2),
            "average_price": round(sum(prices) / len(prices), 2),
            "listing_count": len(prices),
        })

    # Keep file from growing forever on GitHub Pages.
    history = history[-1000:]
    return history


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    watchlist = load_csv("watchlist.csv", ["product_id", "keyword", "type", "enabled"])
    deals = []
    ebay_status = {
        "enabled": ENABLE_EBAY,
        "marketplace": EBAY_MARKETPLACE_ID,
        "results_per_product": EBAY_RESULTS_PER_PRODUCT,
        "last_checked": now,
        "errors": [],
        "searched_keywords": [],
    }

    # Keep manual items visible regardless of API state.
    deals.extend(manual_deals(now))

    if ENABLE_EBAY:
        try:
            token = get_ebay_token()
            for _, product in watchlist.iterrows():
                enabled = clean_string(product.get("enabled", "1"))
                if enabled in ["0", "false", "False", "no", "No"]:
                    continue

                keyword = clean_string(product.get("keyword", ""))
                if not keyword:
                    continue

                ebay_status["searched_keywords"].append(keyword)
                try:
                    listings = search_ebay(keyword, token)
                    for listing in listings:
                        parsed = parse_ebay_listing(product, listing, now)
                        if parsed:
                            deals.append(parsed)
                except Exception as error:
                    message = f"eBay search error for '{keyword}': {error}"
                    print(message)
                    ebay_status["errors"].append(message)
        except Exception as error:
            message = f"eBay auth error: {error}"
            print(message)
            ebay_status["errors"].append(message)

    # Sort by source then price for a cleaner dashboard.
    deals = sorted(deals, key=lambda item: (item.get("product_id", ""), safe_float(item.get("price", 0))))

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, update_history(deals, now))
    save_json(RETAIL_FILE, retail_inventory(now))
    save_json(TIKTOK_FILE, tiktok_videos())
    save_json(EBAY_STATUS_FILE, ebay_status)

    print(f"Saved {len(deals)} total deal rows.")
    print(f"Saved retail inventory rows.")
    print(f"eBay errors: {len(ebay_status['errors'])}")


if __name__ == "__main__":
    main()
