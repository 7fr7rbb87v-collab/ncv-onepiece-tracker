import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from alerts import send_discord_alert
from ebay_source import search_ebay

ROOT = Path(__file__).resolve().parent
WATCHLIST_PATH = ROOT / "watchlist.csv"
MANUAL_LISTINGS_PATH = ROOT / "manual_listings.csv"
DEALS_PATH = ROOT / "deals_found.csv"


def normalize(text: str) -> str:
    return " ".join(str(text).lower().replace("-", " ").split())


def keyword_match(keyword: str, title: str) -> bool:
    # Require meaningful tokens so generic words like "one", "piece", or "sealed"
    # do not trigger bad matches.
    stop_words = {"one", "piece", "card", "cards", "sealed", "booster", "box", "promo", "the"}
    keyword_words = [w for w in normalize(keyword).split() if len(w) > 2 and w not in stop_words]
    title_norm = normalize(title)
    if not keyword_words:
        return False

    # Strong identifiers like set codes should match directly.
    strong_ids = [w for w in keyword_words if any(ch.isdigit() for ch in w)]
    if strong_ids and not any(w in title_norm for w in strong_ids):
        return False

    matches = sum(1 for w in keyword_words if w in title_norm)
    return matches >= max(1, int(len(keyword_words) * 0.6))


def load_manual_listings() -> list[dict]:
    if not MANUAL_LISTINGS_PATH.exists():
        return []
    df = pd.read_csv(MANUAL_LISTINGS_PATH)
    return df.fillna(0).to_dict("records")


def evaluate_listing(watch: dict, listing: dict) -> dict | None:
    if not keyword_match(watch["keyword"], listing["title"]):
        return None

    price = float(listing.get("price", 0) or 0)
    shipping = float(listing.get("shipping", 0) or 0)
    total_cost = price + shipping
    max_buy_price = float(watch["max_buy_price"])
    target_resale = float(watch["target_resale_price"])
    min_profit = float(watch["min_profit"])

    estimated_profit = target_resale - total_cost

    if total_cost <= max_buy_price and estimated_profit >= min_profit:
        return {
            "found_at": datetime.now().isoformat(timespec="seconds"),
            "category": watch["category"],
            "keyword": watch["keyword"],
            "source": listing.get("source", "unknown"),
            "title": listing.get("title", ""),
            "price": price,
            "shipping": shipping,
            "total_cost": total_cost,
            "max_buy_price": max_buy_price,
            "target_resale_price": target_resale,
            "estimated_profit": estimated_profit,
            "url": listing.get("url", ""),
        }
    return None


def save_deals(deals: list[dict]) -> None:
    if not deals:
        return
    new_df = pd.DataFrame(deals)
    if DEALS_PATH.exists():
        old_df = pd.read_csv(DEALS_PATH)
        combined = pd.concat([old_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["title", "url"], keep="last")
    else:
        combined = new_df
    combined.to_csv(DEALS_PATH, index=False)


def run(use_ebay: bool = False, ebay_limit: int = 10) -> list[dict]:
    watchlist = pd.read_csv(WATCHLIST_PATH).fillna("").to_dict("records")
    all_deals = []

    for watch in watchlist:
        listings = load_manual_listings()
        if use_ebay:
            listings.extend(search_ebay(watch["keyword"], limit=ebay_limit))

        for listing in listings:
            deal = evaluate_listing(watch, listing)
            if deal:
                all_deals.append(deal)
                send_discord_alert(deal)

    save_deals(all_deals)
    return all_deals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NCV One Piece card/sealed product deal tracker")
    parser.add_argument("--ebay", action="store_true", help="Use eBay Browse API if EBAY_ACCESS_TOKEN is set")
    parser.add_argument("--limit", type=int, default=10, help="eBay results per keyword")
    args = parser.parse_args()

    deals = run(use_ebay=args.ebay, ebay_limit=args.limit)

    if not deals:
        print("No deals found. Update watchlist prices or add listings.")
    else:
        print(f"Found {len(deals)} deal(s):\n")
        for deal in deals:
            print(f"[{deal['category'].upper()}] {deal['title']}")
            print(f"Cost: ${deal['total_cost']:.2f} | Target: ${deal['target_resale_price']:.2f} | Est. Profit: ${deal['estimated_profit']:.2f}")
            print(f"{deal['url']}\n")
