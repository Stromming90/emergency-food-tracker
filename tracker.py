#!/usr/bin/env python3
"""
Emergency Food Storage Tracker
==============================
Track your emergency food storage: keep a permanent product list,
record purchases with best-before dates, and get desktop alerts
6 months, 3 months and 1 month before each item expires.

Usage:
  python3 tracker.py add-product <name> [--category CAT]
  python3 tracker.py buy <product> <best-before YYYY-MM-DD> [--quantity N]
  python3 tracker.py list-products
  python3 tracker.py inventory [--product NAME]
  python3 tracker.py alerts
  python3 tracker.py check            # meant for cron: prints & notifies

All data lives in CSV files next to this script (products.csv, inventory.csv),
so the whole folder is your git repo — commit it to keep history.
"""

import argparse
import csv
import os
import subprocess
import sys
from datetime import date, datetime

# Same data location as the web app (server.py). In Docker set DATA_DIR=/data.
# By default both the CLI and the web app use a "data/" folder next to the code.
BASE_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
PRODUCTS_CSV = os.path.join(BASE_DIR, "products.csv")
INVENTORY_CSV = os.path.join(BASE_DIR, "inventory.csv")

ALERT_WINDOWS_DAYS = {"6 months": 180, "3 months": 90, "1 month": 30}
PRODUCTS_HEADER = ["name", "category", "added_date"]
INVENTORY_HEADER = ["id", "product", "best_before", "quantity", "added_date"]


# ---------- storage helpers ----------

def ensure_files():
    for path, header in ((PRODUCTS_CSV, PRODUCTS_HEADER), (INVENTORY_CSV, INVENTORY_HEADER)):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(header)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Invalid date '{s}'. Use YYYY-MM-DD.")


def today():
    return date.today()


def next_id(rows):
    return max((int(r["id"]) for r in rows), default=0) + 1


# ---------- commands ----------

def cmd_add_product(args):
    products = read_csv(PRODUCTS_CSV)
    name = args.name.strip()
    if any(p["name"].lower() == name.lower() for p in products):
        sys.exit(f"Product '{name}' is already on the list.")
    products.append({"name": name, "category": args.category or "",
                     "added_date": today().isoformat()})
    products.sort(key=lambda p: p["name"].lower())
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, products)
    print(f"Added product '{name}'.")


def cmd_buy(args):
    products = read_csv(PRODUCTS_CSV)
    name = args.product.strip()
    if not any(p["name"].lower() == name.lower() for p in products):
        sys.exit(f"Unknown product '{name}'. Add it first with: "
                 f"python3 tracker.py add-product \"{name}\"")
    best = parse_date(args.best_before)
    if best < today():
        sys.exit(f"Best-before date {best} is in the past.")
    inv = read_csv(INVENTORY_CSV)
    inv.append({"id": str(next_id(inv)), "product": name,
                "best_before": best.isoformat(),
                "quantity": str(args.quantity), "added_date": today().isoformat()})
    write_csv(INVENTORY_CSV, INVENTORY_HEADER, inv)
    print(f"Recorded {args.quantity} x {name}, best before {best}.")


def cmd_list_products(args):
    products = read_csv(PRODUCTS_CSV)
    if not products:
        print("No products on the list yet. Add some with 'add-product'.")
        return
    print(f"{'Product':30} {'Category':20} Added")
    for p in products:
        print(f"{p['name']:30} {p['category']:20} {p['added_date']}")


def cmd_inventory(args):
    inv = read_csv(INVENTORY_CSV)
    if args.product:
        inv = [r for r in inv if r["product"].lower() == args.product.lower()]
    if not inv:
        print("Inventory is empty.")
        return
    inv.sort(key=lambda r: r["best_before"])
    print(f"{'ID':>3} {'Product':30} {'Qty':>4}  Best before  Days left")
    for r in inv:
        best = parse_date(r["best_before"])
        days = (best - today()).days
        print(f"{r['id']:>3} {r['product']:30} {r['quantity']:>4}  "
              f"{r['best_before']:12}  {days:>4}")


def active_alerts():
    """Return rows (item, window label) for items inside an alert window."""
    alerts = []
    for r in read_csv(INVENTORY_CSV):
        best = parse_date(r["best_before"])
        days = (best - today()).days
        if days < 0:
            alerts.append((r, "EXPIRED"))
        elif days <= ALERT_WINDOWS_DAYS["1 month"]:
            alerts.append((r, "1 month"))
        elif days <= ALERT_WINDOWS_DAYS["3 months"]:
            alerts.append((r, "3 months"))
        elif days <= ALERT_WINDOWS_DAYS["6 months"]:
            alerts.append((r, "6 months"))
    return alerts


def cmd_alerts(args):
    found = active_alerts()
    if not found:
        print("No alerts. Nothing expires within 6 months.")
        return
    for r, window in found:
        best = parse_date(r["best_before"])
        days = (best - today()).days
        if window == "EXPIRED":
            print(f"!! EXPIRED: {r['product']} ({r['quantity']}) expired {-days} days ago")
        else:
            print(f"[{window} alert] {r['product']} ({r['quantity']}) "
                  f"best before {r['best_before']} — {days} days left")


def notify(title, message):
    """Send a desktop notification. Works on Linux and macOS, fails silently."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                            f'display notification "{message}" with title "{title}"'],
                           check=False)
        else:
            subprocess.run(["notify-send", title, message], check=False)
    except OSError:
        pass


def cmd_check(args):
    """For cron: print alerts and raise desktop notifications."""
    found = active_alerts()
    if not found:
        print(f"{today()}: all good, nothing expiring within 6 months.")
        return
    for r, window in found:
        if window == "EXPIRED":
            msg = f"{r['product']} expired! Best before {r['best_before']}."
        else:
            msg = (f"{r['product']} best before {r['best_before']} "
                   f"— {window} warning.")
        print(msg)
        notify("Food storage alert", msg)


# ---------- entry point ----------

def main():
    ensure_files()
    parser = argparse.ArgumentParser(description="Emergency food storage tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-product", help="Add a product to the permanent list")
    p.add_argument("name")
    p.add_argument("--category", default="")
    p.set_defaults(func=cmd_add_product)

    p = sub.add_parser("buy", help="Record a purchase with a best-before date")
    p.add_argument("product")
    p.add_argument("best_before", help="Best before date, YYYY-MM-DD")
    p.add_argument("--quantity", type=int, default=1)
    p.set_defaults(func=cmd_buy)

    p = sub.add_parser("list-products", help="Show the permanent product list")
    p.set_defaults(func=cmd_list_products)

    p = sub.add_parser("inventory", help="Show stock sorted by best-before date")
    p.add_argument("--product")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("alerts", help="Show current expiry alerts")
    p.set_defaults(func=cmd_alerts)

    p = sub.add_parser("check", help="Print alerts and send desktop notifications (for cron)")
    p.set_defaults(func=cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
