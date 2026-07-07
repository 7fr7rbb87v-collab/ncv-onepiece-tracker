import base64
import json
import math
import os
import re
from datetime import datetime, timezone
from statistics import median

import pandas as pd
import requests

DATA_DIR = "data"
DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SOLD_COMPS_FILE = os.path.join(DATA_DIR, "sold_comps.json")
RETAIL_LEADS_FILE = os.path.join(DATA_DIR, "retail_leads.json")
TIKTOK_VIDEOS_FILE = os.path.join(DATA_DIR, "tiktok_videos.json")
EBAY_STATUS_FILE = os.path.join(DATA_DIR, "ebay_status.json")
SOURCE_STATUS_FILE = os.path.join(DATA_DIR, "source_status.json")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        clean_value = str(value).replace("$", "").replace(",", "").strip()
        if clean_value == "":
            return default
        return float(clean_value)
    except Exception:
        return default


def clean(value) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def read_csv_if_exists(path: str, columns):
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def get_ebay_token(client_id: str, client_secret: str) -> str:
    credentials = f"{client_id}:{client_secret}"
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


def get_shipping_cost(item: dict) -> float:
    options = item.get("shippingOptions") or []
    for option in options:
        cost = option.get("shippingCost") or {}
        value = safe_float(cost.get("value"), 0)
        if value >= 0:
            return value
    return 0.0


def get_image(item: dict) -> str:
    image = item.get("image") or {}
    return image.get("imageUrl", "")


def get_seller(item: dict) -> dict:
    seller = item.get("seller") or {}
    return {
        "username": seller.get("username", ""),
        "feedback_score": seller.get("feedbackScore", ""),
        "feedback_percentage": seller.get("feedbackPercentage", ""),
    }


def should_exclude(title: str, exclude_words: str) -> bool:
    title_lower = title.lower()
    words = [word.strip().lower() for word in clean(exclude_words).split(",") if word.strip()]
    return any(word in title_lower for word in words)


def ebay_search(product: dict, token: str, marketplace_id: str) -> list:
    keywords = clean(product.get("keywords"))
    product_limit = safe_float(product.get("max_results"), 0)
    default_limit = safe_float(os.getenv("EBAY_RESULTS_PER_PRODUCT"), 20)
    max_results = int(product_limit or default_limit or 20)
    max_results = max(1, min(max_results, 50))
    sort = os.getenv("EBAY_SORT", "newlyListed") or "newlyListed"
    category = clean(product.get("ebay_category"))

    params = {
        "q": keywords,
        "limit": max_results,
        "sort": sort,
    }
    if category:
        params["category_ids"] = category

    response = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
        },
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("itemSummaries", [])


def convert_ebay_item(product: dict, item: dict, timestamp: str) -> dict:
    price = safe_float((item.get("price") or {}).get("value"), 0)
    shipping = get_shipping_cost(item)
    total_price = round(price + shipping, 2)
    seller = get_seller(item)

    return {
        "product_id": clean(product.get("product_id")),
        "product_name": clean(product.get("product_name")),
        "keyword": clean(product.get("keywords")),
        "type": clean(product.get("type")) or "item",
        "era": clean(product.get("era")) or "unknown",
        "source": "eBay",
        "title": clean(item.get("title")),
        "price": round(price, 2),
        "shipping": round(shipping, 2),
        "total_price": total_price,
        "url": clean(item.get("itemWebUrl")),
        "image": get_image(item),
        "condition": clean(item.get("condition")),
        "seller_username": seller["username"],
        "seller_feedback_score": seller["feedback_score"],
        "seller_feedback_percentage": seller["feedback_percentage"],
        "item_id": item.get("itemId", ""),
        "last_checked": timestamp,
    }


def grade_deal(total_price: float, market_value: float) -> str:
    if market_value <= 0 or total_price <= 0:
        return "No market"
    ratio = total_price / market_value
    if ratio <= 0.70:
        return "A+"
    if ratio <= 0.80:
        return "A"
    if ratio <= 0.90:
        return "B"
    if ratio <= 1.00:
        return "Watch"
    return "Pass"


def add_market_math(listings: list) -> list:
    """
    Calculates buy targets from the product market, not from each listing price.

    Market value = median total active eBay listing price for the product.
    Buy target = 20% under market value.
    Sale target = 35% above market value.
    Estimated profit = sale target minus the actual listing total.
    """
    by_product = {}
    for item in listings:
        by_product.setdefault(item["product_id"], []).append(item)

    output = []
    for _, items in by_product.items():
        totals = sorted([
            safe_float(item.get("total_price"), 0)
            for item in items
            if safe_float(item.get("total_price"), 0) > 0
        ])
        market_value = round(median(totals), 2) if totals else 0
        # Market-based max buy is used to decide whether the listing is actually a deal.
        # Buy target shown on the card is the offer target: 20% under the current listing total.
        market_buy_target = round(market_value * 0.80, 2) if market_value else 0
        sale_target = round(market_value * 1.35, 2) if market_value else 0

        for item in items:
            total_price = safe_float(item.get("total_price"), 0)
            buy_target = round(total_price * 0.80, 2) if total_price else 0
            discount_to_market = round((1 - (total_price / market_value)) * 100, 2) if market_value else 0
            gap_to_market_buy_target = round(market_buy_target - total_price, 2) if market_value else 0
            estimated_profit = round(sale_target - total_price, 2) if market_value else 0
            is_buy_lead = bool(market_value and total_price <= market_buy_target)

            item.update({
                "market_value": market_value,
                "buy_target": buy_target,
                "offer_target": buy_target,
                "market_buy_target": market_buy_target,
                "sale_target": sale_target,
                "gap_to_buy_target": gap_to_market_buy_target,
                "gap_to_market_buy_target": gap_to_market_buy_target,
                "estimated_profit": estimated_profit,
                "is_buy_lead": is_buy_lead,
                "discount_to_market_percent": discount_to_market,
                "deal_grade": grade_deal(total_price, market_value),
            })
            output.append(item)

    grade_rank = {"A+": 0, "A": 1, "B": 2, "Watch": 3, "Pass": 4, "No market": 5}
    return sorted(
        output,
        key=lambda row: (
            not bool(row.get("is_buy_lead")),
            grade_rank.get(row.get("deal_grade"), 9),
            -safe_float(row.get("discount_to_market_percent"), 0),
        ),
    )


def update_history(existing_history: list, listings: list, timestamp: str) -> list:
    by_product = {}
    for item in listings:
        by_product.setdefault(item["product_id"], []).append(item)

    for product_id, items in by_product.items():
        totals = [safe_float(item.get("total_price"), 0) for item in items if safe_float(item.get("total_price"), 0) > 0]
        if not totals:
            continue
        market_value = round(median(totals), 2)
        existing_history.append({
            "product_id": product_id,
            "product_name": items[0].get("product_name", ""),
            "timestamp": timestamp,
            "lowest_active_price": round(min(totals), 2),
            "average_active_price": round(sum(totals) / len(totals), 2),
            "market_value": market_value,
            "market_buy_target": round(market_value * 0.80, 2),
            "sale_target": round(market_value * 1.35, 2),
            "listing_count": len(totals),
        })
    return existing_history[-1000:]


def brave_search(query: str, api_key: str, count: int = 5) -> list:
    if not api_key:
        return []
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        params={"q": query, "count": max(1, min(int(count), 10))},
        timeout=30,
    )
    response.raise_for_status()
    return (response.json().get("web") or {}).get("results", [])


def extract_price(text: str) -> float:
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{2})?)", text or "")
    return safe_float(match.group(1), 0) if match else 0


def build_retail_leads(timestamp: str):
    if not env_bool("ENABLE_RETAIL_SEARCH", False):
        return [], {"enabled": False, "status": "disabled"}

    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    watch = read_csv_if_exists("retail_watchlist.csv", ["product_id", "product_name", "keywords", "retailers", "max_results"])
    leads = []
    errors = []

    for _, product in watch.iterrows():
        try:
            count = int(safe_float(product.get("max_results"), 5))
            results = brave_search(clean(product.get("keywords")), api_key, count=count)
            for result in results:
                title = clean(result.get("title"))
                url = clean(result.get("url"))
                description = clean(result.get("description"))
                price = extract_price(f"{title} {description}")
                leads.append({
                    "product_id": clean(product.get("product_id")),
                    "product_name": clean(product.get("product_name")),
                    "title": title,
                    "url": url,
                    "description": description,
                    "price_signal": price,
                    "buy_target": round(price * 0.80, 2) if price else 0,
                    "offer_target": round(price * 0.80, 2) if price else 0,
                    "market_buy_target": round(price * 0.80, 2) if price else 0,
                    "sale_target": round(price * 1.35, 2) if price else 0,
                    "source": "Search / Retail Lead",
                    "last_checked": timestamp,
                })
        except Exception as error:
            errors.append(str(error))

    return leads, {"enabled": True, "status": "success" if not errors else "partial_error", "errors": errors[:5]}


def tiktok_oembed(url: str) -> dict:
    response = requests.get("https://www.tiktok.com/oembed", params={"url": url}, timeout=20)
    response.raise_for_status()
    return response.json()


def build_tiktok_videos(timestamp: str):
    if not env_bool("ENABLE_TIKTOK_SEARCH", False):
        return [], {"enabled": False, "status": "disabled"}

    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    watch = read_csv_if_exists("tiktok_watchlist.csv", ["product_id", "product_name", "keywords", "max_results"])
    videos = []
    errors = []

    for _, product in watch.iterrows():
        try:
            count = int(safe_float(product.get("max_results"), 5))
            results = brave_search(clean(product.get("keywords")), api_key, count=count)
            for result in results:
                url = clean(result.get("url"))
                if "tiktok.com" not in url:
                    continue
                embed = {}
                try:
                    embed = tiktok_oembed(url)
                except Exception:
                    pass
                videos.append({
                    "product_id": clean(product.get("product_id")),
                    "product_name": clean(product.get("product_name")),
                    "title": embed.get("title") or clean(result.get("title")),
                    "author_name": embed.get("author_name", ""),
                    "thumbnail_url": embed.get("thumbnail_url", ""),
                    "html": embed.get("html", ""),
                    "url": url,
                    "source": "TikTok / Search",
                    "last_checked": timestamp,
                })
        except Exception as error:
            errors.append(str(error))

    return videos, {"enabled": True, "status": "success" if not errors else "partial_error", "errors": errors[:5]}


def run() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = now_utc()
    watchlist = read_csv_if_exists(
        "watchlist.csv",
        ["product_id", "product_name", "type", "era", "keywords", "exclude_words", "ebay_category", "condition_filter", "max_results"],
    )

    enable_ebay = env_bool("ENABLE_EBAY", True)
    marketplace_id = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US") or "EBAY_US"
    client_id = os.getenv("EBAY_CLIENT_ID", "")
    client_secret = os.getenv("EBAY_CLIENT_SECRET", "")

    ebay_status = {
        "enabled": enable_ebay,
        "status": "not_started",
        "marketplace_id": marketplace_id,
        "watchlist_count": int(len(watchlist)),
        "last_checked": timestamp,
    }

    listings = []
    if enable_ebay:
        if not client_id or not client_secret:
            ebay_status.update({
                "status": "missing_credentials",
                "message": "Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET as GitHub Secrets.",
            })
        else:
            try:
                token = get_ebay_token(client_id, client_secret)
                errors = []
                for _, product in watchlist.iterrows():
                    try:
                        items = ebay_search(product, token, marketplace_id)
                        for item in items:
                            listing = convert_ebay_item(product, item, timestamp)
                            if should_exclude(listing.get("title", ""), product.get("exclude_words", "")):
                                continue
                            listings.append(listing)
                    except Exception as product_error:
                        errors.append({"product_id": clean(product.get("product_id")), "error": str(product_error)})

                ebay_status.update({
                    "status": "success" if not errors else "partial_error",
                    "listings_found": len(listings),
                    "errors": errors[:10],
                })
            except Exception as error:
                ebay_status.update({"status": "error", "message": str(error)})
    else:
        ebay_status.update({"status": "disabled"})

    deals = add_market_math(listings)
    history = update_history(load_json(HISTORY_FILE, []), deals, timestamp)
    retail_leads, retail_status = build_retail_leads(timestamp)
    tiktok_videos, tiktok_status = build_tiktok_videos(timestamp)

    source_status = {
        "last_checked": timestamp,
        "ebay": ebay_status,
        "retail_search": retail_status,
        "tiktok_search": tiktok_status,
        "sold_comps": {
            "enabled": env_bool("ENABLE_EBAY_SOLD", False),
            "status": "not_connected_in_this_free_build",
            "message": "eBay sold comps require Marketplace Insights approval. This build estimates market value from active listing median until sold comps are available.",
        },
    }

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)
    save_json(SOLD_COMPS_FILE, [])
    save_json(RETAIL_LEADS_FILE, retail_leads)
    save_json(TIKTOK_VIDEOS_FILE, tiktok_videos)
    save_json(EBAY_STATUS_FILE, ebay_status)
    save_json(SOURCE_STATUS_FILE, source_status)

    print(json.dumps(source_status, indent=2))
    print(f"Saved {len(deals)} eBay listings and {len(history)} history rows.")


if __name__ == "__main__":
    run()
