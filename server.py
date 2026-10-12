#!/usr/bin/env python3
"""
Emergency Food Storage Tracker — Web UI server
==============================================
Zero-dependency web server (Python stdlib only) for the food storage tracker.
Serves a simple web UI and a small JSON API. Designed to run in Docker:

    docker compose up -d
    → http://localhost:8000

Data (products.csv, inventory.csv) lives in /data (mount it as a volume!).
"""

import csv
import json
import os
import re
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")
INVENTORY_CSV = os.path.join(DATA_DIR, "inventory.csv")
PORT = int(os.environ.get("PORT", "8000"))

ALERT_WINDOWS = {"6 months": 180, "3 months": 90, "1 month": 30}
PRODUCTS_HEADER = ["name", "category", "added_date"]
INVENTORY_HEADER = ["id", "product", "best_before", "quantity", "added_date"]


# ---------- storage ----------

def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for path, header in ((PRODUCTS_CSV, PRODUCTS_HEADER), (INVENTORY_CSV, INVENTORY_HEADER)):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(header)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def today():
    return date.today()


def alert_level(best_before):
    days = (best_before - today()).days
    if days < 0:
        return "expired"
    if days <= ALERT_WINDOWS["1 month"]:
        return "1month"
    if days <= ALERT_WINDOWS["3 months"]:
        return "3months"
    if days <= ALERT_WINDOWS["6 months"]:
        return "6months"
    return "ok"


# ---------- model ----------

def add_product(name, category):
    name, category = name.strip(), (category or "").strip()
    if not name:
        raise ValueError("Product name is required.")
    if not re.fullmatch(r"[\w\s.,'’\-()åäöÅÄÖéèàü0-9]+", name, re.UNICODE):
        raise ValueError("Product name contains invalid characters.")
    products = read_csv(PRODUCTS_CSV)
    if any(p["name"].lower() == name.lower() for p in products):
        raise ValueError(f"'{name}' is already on the list.")
    products.append({"name": name, "category": category,
                     "added_date": today().isoformat()})
    products.sort(key=lambda p: p["name"].lower())
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, products)


def buy(product, best_before, quantity):
    product = product.strip()
    if not any(p["name"].lower() == product.lower()
               for p in read_csv(PRODUCTS_CSV)):
        raise ValueError(f"Unknown product '{product}'. Add it to the list first.")
    try:
        best = parse_date(best_before)
    except ValueError:
        raise ValueError("Invalid date. Use YYYY-MM-DD.")
    if best < today():
        raise ValueError("Best-before date is in the past.")
    quantity = max(1, int(quantity))
    inv = read_csv(INVENTORY_CSV)
    inv.append({"id": str(max((int(r["id"]) for r in inv), default=0) + 1),
                "product": product, "best_before": best.isoformat(),
                "quantity": str(quantity), "added_date": today().isoformat()})
    write_csv(INVENTORY_CSV, INVENTORY_HEADER, inv)


def remove_item(item_id):
    inv = read_csv(INVENTORY_CSV)
    remaining = [r for r in inv if r["id"] != str(item_id)]
    if len(remaining) == len(inv):
        raise ValueError("Item not found.")
    write_csv(INVENTORY_CSV, INVENTORY_HEADER, remaining)


def remove_product(name):
    if any(r["product"].lower() == name.lower() for r in read_csv(INVENTORY_CSV)):
        raise ValueError("Product still has items in the inventory; remove them first.")
    products = read_csv(PRODUCTS_CSV)
    remaining = [p for p in products if p["name"].lower() != name.lower()]
    if len(remaining) == len(products):
        raise ValueError("Product not found.")
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, remaining)


def inventory_view():
    rows = []
    for r in read_csv(INVENTORY_CSV):
        best = parse_date(r["best_before"])
        days = (best - today()).days
        rows.append({"id": int(r["id"]), "product": r["product"],
                     "best_before": r["best_before"], "quantity": int(r["quantity"]),
                     "days_left": days, "level": alert_level(best)})
    rows.sort(key=lambda r: r["days_left"])
    return rows


def products_view():
    return read_csv(PRODUCTS_CSV)


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter logs
        print("%s - %s" % (self.address_string(), fmt % args))

    def reply(self, code, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                    self.reply(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self.reply(500, {"error": "index.html missing"})
        elif path == "/api/data":
            self.reply(200, {"products": products_view(),
                             "inventory": inventory_view(),
                             "today": today().isoformat()})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/products":
                add_product(body.get("name", ""), body.get("category", ""))
                self.reply(201, {"ok": True})
            elif path == "/api/buy":
                buy(body.get("product", ""), body.get("best_before", ""),
                    body.get("quantity", 1))
                self.reply(201, {"ok": True})
            else:
                self.reply(404, {"error": "not found"})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            m = re.fullmatch(r"/api/inventory/(\d+)", path)
            if m:
                remove_item(m.group(1))
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/products/(.+)", path)
            if m:
                remove_product(unquote(m.group(1)))
                self.reply(200, {"ok": True})
                return
            self.reply(404, {"error": "not found"})
        except ValueError as e:
            self.reply(400, {"error": str(e)})


def main():
    ensure_files()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Food storage tracker UI: http://0.0.0.0:{PORT}  (data: {DATA_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()
