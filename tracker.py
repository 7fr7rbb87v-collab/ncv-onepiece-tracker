import os
import json
import math
import pandas as pd
from datetime import datetime, timezone

DATA_DIR = "data"
DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

BUY_TARGET_MULTIPLIER = 0.80   # 20% below listed price
SALE_TARGET_MULTIPLIER = 1.35  # 35% above listed price


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
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
        with open(path, "r") as file:
            return json.load(file)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=2)


def load_watchlist():
    if not os.path.exists("watchlist.csv"):
        return pd.DataFrame(columns=["product_id", "keyword", "type"])
    return pd.read_csv("watchlist.csv")


def load_manual_listings():
    if not os.path.exists("manual_listings.csv"):
        return pd.DataFrame(columns=["product_id", "title", "price", "url", "image", "source"])
    return pd.read_csv("manual_listings.csv")


def calculate_targets(price):
    buy_target = round(price * BUY_TARGET_MULTIPLIER, 2)
    sale_target = round(price * SALE_TARGET_MULTIPLIER, 2)
    estimated_spread = round(sale_target - buy_target, 2)
    return buy_target, sale_target, estimated_spread


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    watchlist = load_watchlist()
    manual_listings = load_manual_listings()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    deals = []
    history = load_json(HISTORY_FILE, [])

    for _, product in watchlist.iterrows():
        product_id = clean_string(product.get("product_id", ""))
        keyword = clean_string(product.get("keyword", ""))
        product_type = clean_string(product.get("type", "item"))

        if not product_id:
            continue

        product_manual_listings = manual_listings[
            manual_listings["product_id"].astype(str) == product_id
        ]

        prices = []

        for _, listing in product_manual_listings.iterrows():
            title = clean_string(listing.get("title", ""))
            price = safe_float(listing.get("price", 0))
            url = clean_string(listing.get("url", ""))
            image = clean_string(listing.get("image", ""))
            source = clean_string(listing.get("source", "Manual")) or "Manual"

            if price <= 0:
                continue

            buy_target, sale_target, estimated_spread = calculate_targets(price)
            prices.append(price)

            deals.append({
                "product_id": product_id,
                "keyword": keyword,
                "title": title or keyword,
                "price": round(price, 2),
                "buy_target": buy_target,
                "sale_target": sale_target,
                "estimated_spread": estimated_spread,
                "url": url,
                "image": image,
                "source": source,
                "type": product_type,
                "last_checked": now
            })

        prices = [price for price in prices if price > 0]

        if prices:
            lowest_price = min(prices)
            average_price = sum(prices) / len(prices)
            buy_target, sale_target, estimated_spread = calculate_targets(lowest_price)

            history.append({
                "product_id": product_id,
                "keyword": keyword,
                "timestamp": now,
                "lowest_price": round(lowest_price, 2),
                "average_price": round(average_price, 2),
                "buy_target": buy_target,
                "sale_target": sale_target,
                "estimated_spread": estimated_spread,
                "listing_count": len(prices)
            })

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)

    print(f"Saved {len(deals)} listings.")
    print(f"Updated history for tracked products.")
    print("Buy target = 20% below listed price.")
    print("Sale target = 35% above listed price.")


if __name__ == "__main__":
    main()
