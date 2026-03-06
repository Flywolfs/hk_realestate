#!/usr/bin/env python3
"""
Calculate monthly average price_per_sqft trend for each estate from buy transaction records.
The output covers a fixed global date range [GLOBAL_START, GLOBAL_END].
If a month has no transactions, carry forward the previous month's value.
If there is no prior value available (before the first transaction of an estate),
the earliest known average is back-filled to the beginning.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, date

BUY_DIR = os.path.join(os.path.dirname(__file__), "transaction_record_20260306_trans", "buy")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "monthly_price_trend_20260306.json")

# ── Global date range for all estates ──────────────────────────────────────
GLOBAL_START = date(2025, 1, 1)
GLOBAL_END   = date(2026, 3, 6)


def get_all_months(start_date: date, end_date: date):
    """Generate list of (YYYY-MM) strings from start_date to end_date inclusive."""
    months = []
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        months.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return months


def process_estate(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    transactions = data.get("transactions", [])
    estate_id = data.get("estate_id", os.path.basename(file_path).replace(".json", ""))

    # Collect valid (date, price_per_sqft) pairs within the global range
    valid_records = []
    for tx in transactions:
        price = tx.get("price_per_sqft")
        tx_date = tx.get("date")
        if price is None or tx_date is None:
            continue
        try:
            price = float(price)
        except (ValueError, TypeError):
            continue
        if price <= 0:
            continue
        try:
            parsed_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        # Only keep records within [GLOBAL_START, GLOBAL_END]
        if parsed_date < GLOBAL_START or parsed_date > GLOBAL_END:
            continue
        valid_records.append((parsed_date, price))

    # Use global month list regardless of whether this estate has data
    all_months = get_all_months(GLOBAL_START, GLOBAL_END)

    # Group by month (within global range)
    monthly_prices = defaultdict(list)
    for tx_date, price in valid_records:
        month_key = f"{tx_date.year:04d}-{tx_date.month:02d}"
        monthly_prices[month_key].append(price)

    # Calculate monthly averages
    monthly_avg = {}
    for month_key, prices in monthly_prices.items():
        monthly_avg[month_key] = round(sum(prices) / len(prices), 2)

    if not monthly_avg:
        # No valid data in global range at all — skip this estate
        return estate_id, None

    # Build trend: forward-fill missing months; also back-fill months before
    # the first transaction using the earliest available average.
    trend = {}
    last_value = None
    # We'll do two passes:
    # Pass 1 — forward fill (left to right)
    for month in all_months:
        if month in monthly_avg:
            last_value = monthly_avg[month]
        trend[month] = last_value  # may be None for months before 1st data

    # Pass 2 — back-fill None values at the start with the first non-None value
    first_known = next((trend[m] for m in all_months if trend[m] is not None), None)
    if first_known is not None:
        for month in all_months:
            if trend[month] is None:
                trend[month] = first_known
            else:
                break  # once we hit a real value, no more back-fill needed

    return estate_id, {
        "estate_id": estate_id,
        "global_start": GLOBAL_START.strftime("%Y-%m-%d"),
        "global_end": GLOBAL_END.strftime("%Y-%m-%d"),
        "monthly_price_trend": trend
    }


def main():
    if not os.path.isdir(BUY_DIR):
        print(f"Directory not found: {BUY_DIR}")
        return

    json_files = [f for f in os.listdir(BUY_DIR) if f.endswith(".json")]
    print(f"Found {len(json_files)} estate files in buy directory")

    results = {}
    skipped = 0

    for filename in sorted(json_files):
        file_path = os.path.join(BUY_DIR, filename)
        try:
            estate_id, result = process_estate(file_path)
            if result is None:
                skipped += 1
                continue
            results[estate_id] = result
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            skipped += 1

    print(f"Processed {len(results)} estates, skipped {skipped} (no valid price_per_sqft data)")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
