import os
import json
import pandas as pd
from datetime import datetime, timezone

DATA_DIR = "data"
DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SALES_HISTORY_FILE = os.path.join(DATA_DIR, "sales_history.json")

def safe_float(value, default=0):
    try:
        return float(value)
    except Exception:
        return default

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

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    watchlist = pd.read_csv("watchlist.csv")
    manual_listings = pd.read_csv("manual_listings.csv")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    deals = []
    history = load_json(HISTORY_FILE, [])

    for _, product in watchlist.iterrows():
        product_id = product["product_id"]
        keyword = str(product["keyword"])
        max_buy_price = safe_float(product["max_buy_price"])
        target_resale_price = safe_float(product["target_resale_price"])
        product_type = str(product["type"])

        product_listings = manual_listings[
            manual_listings["product_id"].astype(str) == str(product_id)
        ]

        prices = []

        for _, listing in product_listings.iterrows():
            title = str(listing.get("title", ""))
            price = safe_float(listing.get("price", 0))
            url = str(listing.get("url", ""))
            image = str(listing.get("image", ""))
            source = str(listing.get("source", "Manual"))

            if price <= 0:
                continue

            prices.append(price)

            if price <= max_buy_price:
                estimated_profit = target_resale_price - price

                deals.append({
                    "product_id": product_id,
                    "keyword": keyword,
                    "title": title,
                    "price": round(price, 2),
                    "max_buy_price": round(max_buy_price, 2),
                    "target_resale_price": round(target_resale_price, 2),
                    "estimated_profit": round(estimated_profit, 2),
                    "url": url,
                    "image": image,
                    "source": source,
                    "type": product_type,
                    "last_checked": now
                })

        if prices:
            history.append({
                "product_id": product_id,
                "keyword": keyword,
                "timestamp": now,
                "lowest_price": round(min(prices), 2),
                "average_price": round(sum(prices) / len(prices), 2),
                "listing_count": len(prices)
            })
            def build_sales_history():
    if not os.path.exists("sold_sales.csv"):
        return []

    sales = pd.read_csv("sold_sales.csv")
    sales_history = []

    for _, sale in sales.iterrows():
        sales_history.append({
            "product_id": str(sale["product_id"]),
            "title": str(sale["title"]),
            "sold_price": safe_float(sale["sold_price"]),
            "sold_date": str(sale["sold_date"]),
            "url": str(sale["url"]),
            "source": str(sale["source"])
        })

    return sales_history

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)
    sales_history = build_sales_history()
save_json(SALES_HISTORY_FILE, sales_history)

    print(f"Saved {len(deals)} deals.")
    print(f"Updated history with {len(watchlist)} tracked products.")



if __name__ == "__main__":
    main()
