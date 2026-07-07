import base64
import json
import math
import os
import re
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests

DATA_DIR = "data"
FILES = {
    "deals": os.path.join(DATA_DIR, "deals.json"),
    "ebay_listings": os.path.join(DATA_DIR, "ebay_listings.json"),
    "active_history": os.path.join(DATA_DIR, "active_price_history.json"),
    "sold_history": os.path.join(DATA_DIR, "sold_price_history.json"),
    "tiktok": os.path.join(DATA_DIR, "tiktok_videos.json"),
    "retail": os.path.join(DATA_DIR, "retail_inventory.json"),
    "status": os.path.join(DATA_DIR, "source_status.json"),
}

EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SOLD_SEARCH_URL = "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
TIKTOK_OEMBED_URL = "https://www.tiktok.com/oembed"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(str(value).replace("$", "").replace(",", "").strip())
    except Exception:
        return default


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path: str, data: Any) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path).fillna("")


def split_words(value: str) -> List[str]:
    return [word.strip().lower() for word in clean_string(value).split(",") if word.strip()]


def title_is_allowed(title: str, exclude_words: str) -> bool:
    lower = title.lower()
    return not any(word in lower for word in split_words(exclude_words))


def first_price_from_text(text: str) -> float:
    match = re.search(r"\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text or "")
    if not match:
        return 0.0
    return safe_float(match.group(1))


def normalize_url(url: str) -> str:
    url = clean_string(url)
    if not url:
        return ""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def median(values: List[float]) -> float:
    values = [v for v in values if v and v > 0]
    if not values:
        return 0.0
    return round(float(statistics.median(values)), 2)


def ebay_access_token(status: Dict[str, Any]) -> Optional[str]:
    client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
    client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        status["ebay"] = {
            "enabled": env_bool("ENABLE_EBAY", False),
            "status": "missing_credentials",
            "message": "Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET as GitHub Secrets."
        }
        return None

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }

    try:
        response = requests.post(EBAY_TOKEN_URL, headers=headers, data=data, timeout=25)
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as error:
        status["ebay"] = {
            "enabled": True,
            "status": "token_error",
            "message": str(error),
        }
        return None


def ebay_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US"),
    }


def ebay_item_price(item: Dict[str, Any]) -> float:
    return safe_float((item.get("price") or {}).get("value", 0))


def ebay_shipping_price(item: Dict[str, Any]) -> float:
    shipping_options = item.get("shippingOptions") or []
    if not shipping_options:
        return 0.0
    shipping_cost = shipping_options[0].get("shippingCost") or {}
    return safe_float(shipping_cost.get("value", 0))


def parse_ebay_active_item(item: Dict[str, Any], product: Dict[str, Any], checked_at: str) -> Dict[str, Any]:
    price = ebay_item_price(item)
    shipping = ebay_shipping_price(item)
    total_price = round(price + shipping, 2)
    seller = item.get("seller") or {}
    image = item.get("image") or {}

    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "type": product["type"],
        "era": product["era"],
        "source": "eBay Active",
        "item_id": item.get("itemId", ""),
        "title": item.get("title", ""),
        "price": round(price, 2),
        "shipping": round(shipping, 2),
        "total_price": total_price,
        "currency": (item.get("price") or {}).get("currency", "USD"),
        "image": image.get("imageUrl", ""),
        "url": item.get("itemWebUrl", ""),
        "condition": item.get("condition", ""),
        "buying_options": item.get("buyingOptions", []),
        "seller_username": seller.get("username", ""),
        "seller_feedback_score": seller.get("feedbackScore", ""),
        "seller_feedback_percentage": seller.get("feedbackPercentage", ""),
        "item_location_country": (item.get("itemLocation") or {}).get("country", ""),
        "last_checked": checked_at,
    }


def fetch_ebay_active(product: Dict[str, Any], token: str, status: Dict[str, Any]) -> List[Dict[str, Any]]:
    limit = min(env_int("EBAY_RESULTS_PER_PRODUCT", int(product.get("max_results") or 20)), 200)
    params = {
        "q": product["keywords"],
        "limit": limit,
        "sort": os.getenv("EBAY_SORT", "newlyListed"),
    }
    if clean_string(product.get("ebay_category_id")):
        params["category_ids"] = clean_string(product.get("ebay_category_id"))

    try:
        response = requests.get(EBAY_BROWSE_SEARCH_URL, headers=ebay_headers(token), params=params, timeout=30)
        response.raise_for_status()
        raw_items = response.json().get("itemSummaries", [])
        checked_at = now_utc()
        listings = []
        for item in raw_items:
            title = item.get("title", "")
            if not title_is_allowed(title, product.get("exclude_words", "")):
                continue
            parsed = parse_ebay_active_item(item, product, checked_at)
            if parsed["total_price"] > 0:
                listings.append(parsed)
        return listings
    except Exception as error:
        status.setdefault("ebay_active_errors", []).append({
            "product_id": product["product_id"],
            "message": str(error),
        })
        return []


def parse_ebay_sold_item(item: Dict[str, Any], product: Dict[str, Any], checked_at: str) -> Dict[str, Any]:
    price = safe_float((item.get("price") or item.get("itemPrice") or {}).get("value", 0))
    shipping = ebay_shipping_price(item)
    image = item.get("image") or {}
    seller = item.get("seller") or {}
    sold_date = item.get("itemCreationDate") or item.get("lastSoldDate") or item.get("dateSold") or ""

    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "type": product["type"],
        "era": product["era"],
        "source": "eBay Sold",
        "item_id": item.get("itemId", ""),
        "title": item.get("title", ""),
        "sold_price": round(price, 2),
        "shipping": round(shipping, 2),
        "total_sold_price": round(price + shipping, 2),
        "currency": (item.get("price") or {}).get("currency", "USD"),
        "image": image.get("imageUrl", ""),
        "url": item.get("itemWebUrl", ""),
        "condition": item.get("condition", ""),
        "seller_username": seller.get("username", ""),
        "sold_date": sold_date,
        "last_checked": checked_at,
    }


def fetch_ebay_sold(product: Dict[str, Any], token: str, status: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not env_bool("ENABLE_EBAY_SOLD", False):
        return []

    limit = min(env_int("EBAY_SOLD_RESULTS_PER_PRODUCT", 20), 200)
    params = {
        "q": product["keywords"],
        "limit": limit,
    }
    if clean_string(product.get("ebay_category_id")):
        params["category_ids"] = clean_string(product.get("ebay_category_id"))

    try:
        response = requests.get(EBAY_SOLD_SEARCH_URL, headers=ebay_headers(token), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_items = data.get("itemSales") or data.get("itemSummaries") or []
        checked_at = now_utc()
        sold = []
        for item in raw_items:
            title = item.get("title", "")
            if not title_is_allowed(title, product.get("exclude_words", "")):
                continue
            parsed = parse_ebay_sold_item(item, product, checked_at)
            if parsed["total_sold_price"] > 0:
                sold.append(parsed)
        return sold
    except Exception as error:
        status.setdefault("ebay_sold_errors", []).append({
            "product_id": product["product_id"],
            "message": str(error),
            "note": "Marketplace Insights is limited-release. Active listings still work if Browse API access is valid."
        })
        return []


def build_market_summary(product: Dict[str, Any], active: List[Dict[str, Any]], sold: List[Dict[str, Any]], checked_at: str) -> Dict[str, Any]:
    active_prices = [item["total_price"] for item in active if item.get("product_id") == product["product_id"]]
    sold_prices = [item["total_sold_price"] for item in sold if item.get("product_id") == product["product_id"]]

    median_sold = median(sold_prices)
    median_active = median(active_prices)
    market_value = median_sold or median_active
    value_source = "sold_median" if median_sold else "active_median"

    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "type": product["type"],
        "era": product["era"],
        "timestamp": checked_at,
        "market_value": round(market_value, 2),
        "market_value_source": value_source if market_value else "unavailable",
        "buy_target": round(market_value * 0.80, 2) if market_value else 0,
        "sale_target": round(market_value * 1.35, 2) if market_value else 0,
        "lowest_active_price": round(min(active_prices), 2) if active_prices else 0,
        "average_active_price": round(sum(active_prices) / len(active_prices), 2) if active_prices else 0,
        "median_active_price": median_active,
        "median_sold_price": median_sold,
        "active_listing_count": len(active_prices),
        "sold_comp_count": len(sold_prices),
    }


def grade_deal(total_price: float, market_value: float) -> str:
    if total_price <= 0 or market_value <= 0:
        return "No market value"
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


def build_deals(active: List[Dict[str, Any]], summaries: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    deals = []
    for item in active:
        summary = summaries.get(item["product_id"], {})
        market_value = safe_float(summary.get("market_value"))
        buy_target = safe_float(summary.get("buy_target"))
        sale_target = safe_float(summary.get("sale_target"))
        total_price = safe_float(item.get("total_price"))
        grade = grade_deal(total_price, market_value)
        expected_profit = round(sale_target - total_price, 2) if sale_target else 0
        discount_pct = round((1 - (total_price / market_value)) * 100, 1) if market_value else 0

        lead = {
            **item,
            "market_value": market_value,
            "market_value_source": summary.get("market_value_source", "unavailable"),
            "buy_target": buy_target,
            "sale_target": sale_target,
            "expected_profit_at_sale_target": expected_profit,
            "discount_to_market_pct": discount_pct,
            "deal_grade": grade,
        }
        deals.append(lead)

    grade_rank = {"A+": 0, "A": 1, "B": 2, "Watch": 3, "Pass": 4, "No market value": 5}
    return sorted(deals, key=lambda x: (grade_rank.get(x.get("deal_grade"), 99), -safe_float(x.get("expected_profit_at_sale_target"))))


def brave_search(query: str, count: int, status: Dict[str, Any]) -> List[Dict[str, Any]]:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        status.setdefault("brave", {"status": "missing_credentials", "message": "Add BRAVE_SEARCH_API_KEY to enable source discovery."})
        return []
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": key,
    }
    params = {
        "q": query,
        "count": min(max(count, 1), 20),
        "search_lang": "en",
        "country": "US",
        "safesearch": "moderate",
    }
    try:
        response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=25)
        response.raise_for_status()
        return (response.json().get("web") or {}).get("results") or []
    except Exception as error:
        status.setdefault("brave_errors", []).append({"query": query, "message": str(error)})
        return []


def build_retail_inventory(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not env_bool("ENABLE_RETAIL_SEARCH", False):
        return []
    watchlist = read_csv("retail_watchlist.csv")
    results = []
    checked_at = now_utc()
    seen = set()
    for _, row in watchlist.iterrows():
        retailer = clean_string(row.get("retailer", "Retail"))
        query = clean_string(row.get("query", ""))
        max_results = int(safe_float(row.get("max_results", 8), 8))
        if not query:
            continue
        for item in brave_search(query, max_results, status):
            url = normalize_url(item.get("url", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            text = f"{item.get('title', '')} {item.get('description', '')}"
            lowered = text.lower()
            if "out of stock" in lowered or "sold out" in lowered:
                stock_status = "out_of_stock"
            elif "preorder" in lowered or "pre-order" in lowered:
                stock_status = "preorder"
            elif "available" in lowered or "$" in lowered:
                stock_status = "possible_available"
            else:
                stock_status = "source_check_required"
            price = first_price_from_text(text)
            results.append({
                "retailer": retailer,
                "title": item.get("title", ""),
                "price": round(price, 2) if price else 0,
                "buy_target": round(price * 0.80, 2) if price else 0,
                "sale_target": round(price * 1.35, 2) if price else 0,
                "url": url,
                "description": item.get("description", ""),
                "stock_status": stock_status,
                "source": "Brave Search",
                "last_checked": checked_at,
            })
    return results


def discover_tiktok_videos(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not env_bool("ENABLE_TIKTOK_SEARCH", False):
        return []
    watchlist = read_csv("tiktok_watchlist.csv")
    videos = []
    seen = set()
    checked_at = now_utc()
    for _, row in watchlist.iterrows():
        product_id = clean_string(row.get("product_id", ""))
        query = clean_string(row.get("query", ""))
        max_results = int(safe_float(row.get("max_results", 6), 6))
        if not query:
            continue
        for result in brave_search(query, max_results, status):
            url = normalize_url(result.get("url", ""))
            if "tiktok.com" not in url or "/video/" not in url or url in seen:
                continue
            seen.add(url)
            video = {
                "product_id": product_id,
                "source": "TikTok oEmbed",
                "url": url,
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "author_name": "",
                "thumbnail_url": "",
                "embed_html": "",
                "last_checked": checked_at,
            }
            try:
                response = requests.get(TIKTOK_OEMBED_URL, params={"url": url}, timeout=20)
                response.raise_for_status()
                data = response.json()
                video.update({
                    "title": data.get("title") or video["title"],
                    "author_name": data.get("author_name", ""),
                    "thumbnail_url": data.get("thumbnail_url", ""),
                    "embed_html": data.get("html", ""),
                })
            except Exception as error:
                video["oembed_error"] = str(error)
            videos.append(video)
            time.sleep(0.2)
    return videos


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    status: Dict[str, Any] = {
        "last_run": now_utc(),
        "mode": "source_pull_only_no_manual_listings",
    }

    products_df = read_csv("watchlist.csv")
    products = []
    for _, row in products_df.iterrows():
        products.append({
            "product_id": clean_string(row.get("product_id", "")),
            "product_name": clean_string(row.get("product_name", "")),
            "type": clean_string(row.get("type", "single")),
            "era": clean_string(row.get("era", "modern")),
            "keywords": clean_string(row.get("keywords", "")),
            "exclude_words": clean_string(row.get("exclude_words", "")),
            "ebay_category_id": clean_string(row.get("ebay_category_id", "")),
            "max_results": clean_string(row.get("max_results", "20")),
        })
    products = [p for p in products if p["product_id"] and p["keywords"]]

    active_listings: List[Dict[str, Any]] = []
    sold_records: List[Dict[str, Any]] = []

    if env_bool("ENABLE_EBAY", False):
        token = ebay_access_token(status)
        if token:
            for product in products:
                active_listings.extend(fetch_ebay_active(product, token, status))
                sold_records.extend(fetch_ebay_sold(product, token, status))
            status["ebay"] = {
                "enabled": True,
                "status": "success" if active_listings or not status.get("ebay_active_errors") else "no_results_or_errors",
                "active_listing_count": len(active_listings),
                "sold_record_count": len(sold_records),
                "sold_enabled": env_bool("ENABLE_EBAY_SOLD", False),
            }
    else:
        status["ebay"] = {"enabled": False, "status": "disabled", "message": "Set ENABLE_EBAY=1 in GitHub Variables."}

    checked_at = now_utc()
    product_summaries = {}
    new_active_history = []
    for product in products:
        summary = build_market_summary(product, active_listings, sold_records, checked_at)
        product_summaries[product["product_id"]] = summary
        new_active_history.append(summary)

    old_active_history = load_json(FILES["active_history"], [])
    active_history = (old_active_history + new_active_history)[-5000:]

    old_sold_history = load_json(FILES["sold_history"], [])
    existing_sold_keys = {f"{x.get('product_id')}::{x.get('item_id')}::{x.get('sold_date')}" for x in old_sold_history}
    merged_sold = list(old_sold_history)
    for record in sold_records:
        key = f"{record.get('product_id')}::{record.get('item_id')}::{record.get('sold_date')}"
        if key not in existing_sold_keys:
            merged_sold.append(record)
            existing_sold_keys.add(key)
    merged_sold = merged_sold[-5000:]

    deals = build_deals(active_listings, product_summaries)
    retail = build_retail_inventory(status)
    tiktok = discover_tiktok_videos(status)

    status["outputs"] = {
        "products_tracked": len(products),
        "deals": len(deals),
        "active_history_points_added": len(new_active_history),
        "retail_results": len(retail),
        "tiktok_videos": len(tiktok),
    }

    save_json(FILES["ebay_listings"], active_listings)
    save_json(FILES["deals"], deals)
    save_json(FILES["active_history"], active_history)
    save_json(FILES["sold_history"], merged_sold)
    save_json(FILES["retail"], retail)
    save_json(FILES["tiktok"], tiktok)
    save_json(FILES["status"], status)

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
