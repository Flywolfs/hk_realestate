#!/usr/bin/env python3
"""
Aggregate transaction data for the HK Property Agent.

Processes buy and rent transaction records to produce three output files:
1. monthly_price_trend.json — monthly average price_per_sqft per estate (with forward/back-fill)
2. monthly_sales_volume.json — monthly transaction count + avg prices per estate
3. rental_summary.json — recent rental records + avg rent per estate

The script auto-detects the latest transaction_record_*_trans directory,
or you can pass a specific directory as a command-line argument.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Global date range ──────────────────────────────────────────────────────
GLOBAL_START = date(2025, 1, 1)


def _find_latest_trans_dir():
    """Auto-detect the latest transaction_record_*_trans directory."""
    pattern = re.compile(r'^transaction_record_(\d{8})_trans$')
    candidates = []
    for name in os.listdir(SCRIPT_DIR):
        m = pattern.match(name)
        if m:
            full = os.path.join(SCRIPT_DIR, name)
            if os.path.isdir(full):
                candidates.append((m.group(1), full))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]  # (date_str, path)


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


def process_buy_estate(file_path: str, global_end: date):
    """
    Process a buy transaction file.
    Returns (estate_id, price_trend_data, volume_data) or (estate_id, None, None).

    price_trend_data: monthly average price_per_sqft with forward/back-fill
    volume_data: monthly count, avg_price, avg_unit_price (raw, no fill)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    transactions = data.get("transactions", [])
    estate_id = data.get("estate_id", os.path.basename(file_path).replace(".json", ""))

    # Collect valid records
    valid_records = []  # (parsed_date, price_per_sqft, total_price)
    for tx in transactions:
        price_psf = tx.get("price_per_sqft")
        tx_date = tx.get("date")
        total_price = tx.get("total_price")
        if tx_date is None:
            continue
        try:
            parsed_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if parsed_date < GLOBAL_START or parsed_date > global_end:
            continue

        psf = None
        if price_psf is not None:
            try:
                psf = float(price_psf)
                if psf <= 0:
                    psf = None
            except (ValueError, TypeError):
                psf = None

        tp = None
        if total_price is not None:
            try:
                tp = float(total_price)
                if tp <= 0:
                    tp = None
            except (ValueError, TypeError):
                tp = None

        valid_records.append((parsed_date, psf, tp))

    if not valid_records:
        return estate_id, None, None

    all_months = get_all_months(GLOBAL_START, global_end)

    # Group by month
    monthly_psf = defaultdict(list)       # price_per_sqft values
    monthly_total = defaultdict(list)     # total_price values
    monthly_count = defaultdict(int)      # transaction count

    for parsed_date, psf, tp in valid_records:
        month_key = f"{parsed_date.year:04d}-{parsed_date.month:02d}"
        monthly_count[month_key] += 1
        if psf is not None:
            monthly_psf[month_key].append(psf)
        if tp is not None:
            monthly_total[month_key].append(tp)

    # ── Price trend (with forward/back-fill) ──
    monthly_avg_psf = {}
    for month_key, prices in monthly_psf.items():
        monthly_avg_psf[month_key] = round(sum(prices) / len(prices), 2)

    price_trend_data = None
    if monthly_avg_psf:
        trend = {}
        last_value = None
        for month in all_months:
            if month in monthly_avg_psf:
                last_value = monthly_avg_psf[month]
            trend[month] = last_value

        first_known = next((trend[m] for m in all_months if trend[m] is not None), None)
        if first_known is not None:
            for month in all_months:
                if trend[month] is None:
                    trend[month] = first_known
                else:
                    break

        price_trend_data = {
            "estate_id": estate_id,
            "global_start": GLOBAL_START.strftime("%Y-%m-%d"),
            "global_end": global_end.strftime("%Y-%m-%d"),
            "monthly_price_trend": trend,
        }

    # ── Volume data (raw, no fill) ──
    volume_data = {}
    for month_key in sorted(monthly_count.keys()):
        cnt = monthly_count[month_key]
        avg_price = round(sum(monthly_total[month_key]) / len(monthly_total[month_key])) if monthly_total[month_key] else None
        avg_unit_price = round(sum(monthly_psf[month_key]) / len(monthly_psf[month_key])) if monthly_psf[month_key] else None
        volume_data[month_key] = {
            "count": cnt,
            "avg_price": avg_price,
            "avg_unit_price": avg_unit_price,
        }

    return estate_id, price_trend_data, volume_data


def process_rent_estate(file_path: str, global_end: date):
    """
    Process a rent transaction file.
    Returns (estate_id, rental_summary) or (estate_id, None).

    rental_summary: recent_rentals list, avg_rent, rent_per_sqft
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    transactions = data.get("transactions", [])
    estate_id = data.get("estate_id", os.path.basename(file_path).replace(".json", ""))

    valid_records = []
    for tx in transactions:
        tx_date = tx.get("date")
        rent = tx.get("total_price")
        if tx_date is None or rent is None:
            continue
        try:
            parsed_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
            rent = float(rent)
        except (ValueError, TypeError):
            continue
        if rent <= 0 or parsed_date < GLOBAL_START or parsed_date > global_end:
            continue

        area = tx.get("area")
        rpsf = tx.get("rent_per_sqft")
        unit_loc = tx.get("unit_location", "")

        valid_records.append({
            "date": tx_date,
            "price": rent,
            "area": area,
            "rent_per_sqft": rpsf,
            "unit_location": unit_loc.strip(),
        })

    if not valid_records:
        return estate_id, None

    # Sort by date descending, keep recent 20 records
    valid_records.sort(key=lambda x: x["date"], reverse=True)
    recent = valid_records[:20]

    # Calculate averages
    rents = [r["price"] for r in valid_records]
    avg_rent = round(sum(rents) / len(rents))

    rpsf_values = [r["rent_per_sqft"] for r in valid_records if r["rent_per_sqft"]]
    avg_rpsf = round(sum(rpsf_values) / len(rpsf_values), 1) if rpsf_values else None

    return estate_id, {
        "recent_rentals": [
            {"date": r["date"], "price": r["price"], "unit_location": r["unit_location"]}
            for r in recent
        ],
        "avg_rent": avg_rent,
        "rent_per_sqft": avg_rpsf,
        "total_records": len(valid_records),
    }


def main():
    # Determine data directory
    if len(sys.argv) > 1:
        trans_dir = sys.argv[1]
        date_str = os.path.basename(trans_dir).replace("transaction_record_", "").replace("_trans", "")
    else:
        date_str, trans_dir = _find_latest_trans_dir()
        if trans_dir is None:
            print("No transaction_record_*_trans directory found.")
            return

    buy_dir = os.path.join(trans_dir, "buy")
    rent_dir = os.path.join(trans_dir, "rent")

    # Parse global end date from directory name
    try:
        global_end = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        global_end = date.today()

    print(f"Data directory: {trans_dir}")
    print(f"Date range: {GLOBAL_START} to {global_end}")

    # ── Process buy transactions ──────────────────────────────────────────
    price_trend_results = {}
    volume_results = {}
    buy_skipped = 0

    if os.path.isdir(buy_dir):
        buy_files = [f for f in os.listdir(buy_dir) if f.endswith(".json")]
        print(f"\nProcessing {len(buy_files)} buy transaction files...")

        for filename in sorted(buy_files):
            file_path = os.path.join(buy_dir, filename)
            try:
                estate_id, price_data, vol_data = process_buy_estate(file_path, global_end)
                if price_data:
                    price_trend_results[estate_id] = price_data
                if vol_data:
                    volume_results[estate_id] = vol_data
                if not price_data and not vol_data:
                    buy_skipped += 1
            except Exception as e:
                print(f"  Error processing buy/{filename}: {e}")
                buy_skipped += 1

        print(f"  Price trends: {len(price_trend_results)} estates")
        print(f"  Volume data: {len(volume_results)} estates")
        print(f"  Skipped: {buy_skipped}")
    else:
        print(f"Buy directory not found: {buy_dir}")

    # ── Process rent transactions ─────────────────────────────────────────
    rental_results = {}
    rent_skipped = 0

    if os.path.isdir(rent_dir):
        rent_files = [f for f in os.listdir(rent_dir) if f.endswith(".json")]
        print(f"\nProcessing {len(rent_files)} rent transaction files...")

        for filename in sorted(rent_files):
            file_path = os.path.join(rent_dir, filename)
            try:
                estate_id, rental_data = process_rent_estate(file_path, global_end)
                if rental_data:
                    rental_results[estate_id] = rental_data
                else:
                    rent_skipped += 1
            except Exception as e:
                print(f"  Error processing rent/{filename}: {e}")
                rent_skipped += 1

        print(f"  Rental summaries: {len(rental_results)} estates")
        print(f"  Skipped: {rent_skipped}")
    else:
        print(f"Rent directory not found: {rent_dir}")

    # ── Write output files ────────────────────────────────────────────────
    output_configs = [
        (
            price_trend_results,
            f"monthly_price_trend_{date_str}.json",
            "monthly_price_trend.json",
        ),
        (
            {"update_date": date_str, "data": volume_results},
            f"monthly_sales_volume_{date_str}.json",
            "monthly_sales_volume.json",
        ),
        (
            {"update_date": date_str, "data": rental_results},
            f"rental_summary_{date_str}.json",
            "rental_summary.json",
        ),
    ]

    print(f"\nWriting output files...")
    for data_obj, dated_name, latest_name in output_configs:
        # Write dated version (archival)
        dated_path = os.path.join(SCRIPT_DIR, dated_name)
        with open(dated_path, "w", encoding="utf-8") as f:
            json.dump(data_obj, f, ensure_ascii=False, indent=2)
        print(f"  {dated_name}")

        # Write latest version (for agent to load)
        latest_path = os.path.join(SCRIPT_DIR, latest_name)
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data_obj, f, ensure_ascii=False, indent=2)
        print(f"  {latest_name}")

    print("\nDone!")


if __name__ == "__main__":
    main()
