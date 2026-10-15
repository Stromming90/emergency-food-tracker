#!/usr/bin/env python3
"""
Emergency Food Storage Tracker — Web UI server (v2.8.0)
=====================================================
Zero-dependency web server (Python stdlib only).

v2.8:
- Bundled Swedish emergency-food barcode defaults
  (data/barcode-defaults.json, 1747 products): on first start they are
  seeded into the global product list and the barcode mappings. Existing
  products/mappings are never overwritten; admin deletions stick.
- Inventory scan: the web/app UI has a separate "Scan" in the Household →
  Inventory section that adds a scanned product to the inventory with an
  arbitrary quantity (distinct from the header scan that fills the
  product-list "Buy" form)

v2.7.3:
- /app.apk download is versioned (emergency-food-tracker-<ver>.apk) and
  served with no-store, so a stale APK can never be confused with a new one

v2.7:
- Android app (WebView) with camera barcode scanning, served at /app.apk
- Barcodes main tab (global admin): map scanned barcode IDs to products
- /api/barcode lookup + /api/admin/barcodes CRUD
- "Get for Android" download button on the site

v2.6:
- OIDC display name: configurable, shown on the SSO login button
- Authentication tab: name field + one checkbox per row
- Users/Households/Authentication settings: tidier layout

v2.5:
- Authentication tab: enable/disable SSO login, optional password login lockout
- Editable type/category options (global admin)
- Inventory view carries type/category/size from the product
- Household membership editable after creation
- Refreshed default food types/categories

v2.4:
- Product model: type (curated), category (sub-category), size
- Per-user API keys with regeneration
- Roles: global admin / household admin / user
- Household admin: edit product list, migrate inventory, manage users
  in their households
- Any user can create a household (becomes its household admin)
- No implicit 'default' household

Environment variables:
  DATA_DIR   household data root         (default ./data)
  CONFIG_DIR users & settings            (default ./config)
  PORT       listen port                 (default 4500)
  OIDC_*     optional OIDC overrides
"""

import base64
import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(APP_DIR, "data"))
CONFIG_DIR = os.environ.get("CONFIG_DIR", os.path.join(APP_DIR, "config"))
STATIC_DIR = os.path.join(APP_DIR, "static")
APP_APK_B64 = os.path.join(APP_DIR, "app", "eft-app.apk.b64")  # v2.7 android app
APP_APK_BYTES = None                      # decoded once on first request
# v2.8: bundled Swedish emergency-food barcode defaults. The file lives next
# to server.py (image path in Docker), NOT inside DATA_DIR, so a mounted
# /data volume can never shadow it.
BARCODE_DEFAULTS_FILE = os.path.join(APP_DIR, "data", "barcode-defaults.json")
BARCODE_DEFAULTS_SEED = "v2.8"             # bump to re-seed after data updates
USERS_FILE = os.path.join(CONFIG_DIR, "users.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")   # global product list
PORT = int(os.environ.get("PORT", "4500"))

# v2.4.2: outbound OIDC requests use a browser-like User-Agent so that
# bot-protection layers in front of OIDC providers (e.g. Cloudflare
# Bot Fight Mode, which blocks "Python-urllib") do not break SSO.
OIDC_HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}

ALERT_WINDOWS = {"6months": 180, "3months": 90, "1month": 30}
# v2.4: type + category (sub-category) + size per product
PRODUCTS_HEADER = ["name", "manufacturer", "type", "category", "size", "added_date"]
INVENTORY_HEADER = ["id", "product", "manufacturer", "best_before", "quantity", "added_date"]

SESSIONS = {}
SESSION_TTL = 7 * 24 * 3600

# v2.5: default food TYPES. Instances may customise these via the admin
# UI; the live set is stored in config.json ("food_types"). Each type
# carries suggested sub-categories ("categories") for products.
DEFAULT_FOOD_TYPES = [
    {"id": "dry_staples_carbs", "label": "Dry staples & carbohydrates",
     "storage": "cool_dry", "shelf_life_months": [12, 36],
     "categories": ["pasta", "rice", "couscous", "flour", "oats", "rolled grains",
                    "crispbread", "flatbread", "potato flakes", "mashed potato powder",
                    "muesli", "granola", "porridge oats"]},
    {"id": "canned_ready_foods", "label": "Canned & jarred foods",
     "storage": "pantry", "shelf_life_months": [12, 48],
     "categories": ["ravioli", "canned soups", "chili", "stew", "baked beans",
                    "beans in tomato sauce", "chickpeas", "lentils", "corn", "peas",
                    "beetroot", "potatoes", "carrots", "sauce", "canned fruit",
                    "applesauce", "berry purée"]},
    {"id": "protein_sources", "label": "Protein",
     "storage": "pantry", "shelf_life_months": [6, 24],
     "categories": ["peanut butter", "nut butters", "nuts", "seeds", "powdered milk",
                    "UHT milk", "plant-based milk", "cured meats (salami, jerky)",
                    "hard cheese (wax/vacuum)", "eggs", "shelf-stable tofu",
                    "canned fish (tuna, mackerel, sardines, herring)"]},
    {"id": "fats_cooking", "label": "Fats & cooking",
     "storage": "cool_dry", "shelf_life_months": [6, 18],
     "categories": ["cooking oil", "olive oil", "butter", "ghee", "hard margarine",
                    "bouillon cubes", "stock powder"]},
    {"id": "seasonings_sweeteners", "label": "Extras & sweeteners",
     "storage": "pantry", "shelf_life_months": [24, 60],
     "categories": ["salt", "sugar", "honey", "jam"]},
    {"id": "beverages", "label": "Beverages",
     "storage": "cool_dry", "shelf_life_months": [12, 36],
     "categories": ["coffee", "tea", "chocolate powder", "water"]},
    {"id": "instant_meals", "label": "Instant meals (just add water)",
     "storage": "pantry", "shelf_life_months": [12, 36],
     "categories": ["freeze-dried meals", "cup noodles", "instant soups"]},
    {"id": "snacks", "label": "Snacks",
     "storage": "cool_dry", "shelf_life_months": [6, 18],
     "categories": ["chocolate", "dried fruit", "salted nuts", "roasted snacks"]},
    {"id": "supplements", "label": "Supplements",
     "storage": "cool_dry", "shelf_life_months": [12, 36],
     "categories": ["multivitamins"]},
]


# ======================= small utilities =======================

def now():
    return int(time.time())


def today():
    return date.today()


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9åäö\-_]+", "-", s, flags=re.UNICODE)
    return s.strip("-")


def valid_name(s):
    return bool(re.fullmatch(r"[\w\s.,'’\-()åäöÅÄÖéèàü0-9]*", s or "", re.UNICODE))


def valid_label(s):
    # type/category labels may additionally contain & and :
    return bool(re.fullmatch(r"[\w\s.,'’\-()/&:åäöÅÄÖéèàü0-9]*", s or "", re.UNICODE))


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


# ======================= config / users / sessions =======================

def get_config():
    cfg = load_json(CONFIG_FILE, {})
    oidc = cfg.setdefault("oidc", {})
    for env_key, key in (("OIDC_ISSUER", "issuer"), ("OIDC_CLIENT_ID", "client_id"),
                         ("OIDC_CLIENT_SECRET", "client_secret")):
        if os.environ.get(env_key):
            oidc[key] = os.environ[env_key]
    if os.environ.get("OIDC_ADMIN_EMAILS"):
        oidc["admin_emails"] = [e.strip() for e in os.environ["OIDC_ADMIN_EMAILS"].split(",") if e.strip()]
    oidc.setdefault("admin_emails", [])
    auth = cfg.setdefault("auth", {})
    auth.setdefault("sso_login", True)        # v2.5: SSO login toggle
    auth.setdefault("password_login", True)   # v2.5: password login toggle
    cfg.setdefault("barcodes", {})            # v2.7: barcode -> product mappings
    save_json(CONFIG_FILE, cfg)
    return cfg


def get_food_types():
    """Live food types (config.json, falls back to the built-in defaults)."""
    types = get_config().get("food_types")
    if isinstance(types, list) and types:
        return types
    return DEFAULT_FOOD_TYPES


def oidc_configured():
    oidc = get_config()["oidc"]
    return bool(oidc.get("issuer") and oidc.get("client_id"))


def oidc_enabled():
    """True if SSO login is available (configured AND not switched off)."""
    return oidc_configured() and get_config()["auth"].get("sso_login", True) is not False


def password_login_enabled():
    """Password login can only be disabled while SSO login is available."""
    if not oidc_enabled():
        return True
    return get_config()["auth"].get("password_login", True) is not False


def oidc_discovery(oidc):
    if "endpoints" in oidc:
        return oidc["endpoints"]
    base = oidc["issuer"].rstrip("/")
    url = base + "/.well-known/openid-configuration"
    try:
        req = urllib.request.Request(url, headers=OIDC_HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            doc = json.loads(r.read().decode())
        eps = {"authorize": doc["authorization_endpoint"],
               "token": doc["token_endpoint"],
               "userinfo": doc.get("userinfo_endpoint")}
    except Exception as e:
        raise ValueError(f"OIDC discovery failed for {url}: {e}")
    cfg = get_config()
    cfg["oidc"]["endpoints"] = eps
    save_json(CONFIG_FILE, cfg)
    return eps


def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 100_000)
    return salt, digest.hex()


def normalize_user(u):
    """Migrate old user records to the v2.4 role model and ensure an API key."""
    changed = False
    if "role" not in u:
        u["role"] = "global_admin" if u.get("is_admin") else "user"
        changed = True
    if "admin_households" not in u:
        u["admin_households"] = []
        changed = True
    if not u.get("api_key"):
        u["api_key"] = secrets.token_urlsafe(24)
        changed = True
    return changed


def get_users():
    data = load_json(USERS_FILE, {"users": []})
    changed = any(normalize_user(u) for u in data["users"])
    if changed:
        save_json(USERS_FILE, data)
    return data


def save_users(u):
    save_json(USERS_FILE, u)


def user_count():
    return len(get_users()["users"])


def find_user(username):
    for u in get_users()["users"]:
        if u["username"].lower() == username.lower():
            return u
    return None


def find_user_by_api_key(key):
    for u in get_users()["users"]:
        if hmac.compare_digest(u.get("api_key", ""), key):
            return u
    return None


def check_password(user, pw):
    try:
        salt, expect = user["password"].split("$", 1)
    except (KeyError, ValueError):
        return False
    _, got = hash_password(pw, salt)
    return hmac.compare_digest(expect, got)


def create_user(username, password, role="user", households=None,
                admin_households=None, oidc_sub=None, email=None):
    if not valid_name(username) or not username.strip():
        raise ValueError("Invalid username.")
    if len(username) > 40:
        raise ValueError("Username too long.")
    if find_user(username):
        raise ValueError("User already exists.")
    if password and len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if role not in ("user", "global_admin"):
        raise ValueError("Invalid role.")
    households = households or []
    if not households and role != "global_admin":
        raise ValueError("A user needs at least one household.")
    salt, ph = hash_password(password) if password else ("", "")
    users = get_users()
    users["users"].append({
        "username": username.strip(),
        "password": f"{salt}${ph}" if ph else "",
        "role": role,
        "households": households,
        "admin_households": [h for h in (admin_households or []) if h in households] if role == "user" else [],
        "api_key": secrets.token_urlsafe(24),
        "oidc_sub": oidc_sub,
        "email": email,
    })
    save_users(users)


def create_session(username):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"username": username, "expires": now() + SESSION_TTL}
    return token


def session_user(token):
    s = SESSIONS.get(token)
    if not s or s["expires"] < now():
        SESSIONS.pop(token, None)
        return None
    return find_user(s["username"])


def current_user(handler):
    cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    token = cookie.get("session").value if cookie.get("session") else None
    return session_user(token) if token else None


class AuthError(Exception):
    pass


def require_user(handler):
    user = current_user(handler)
    if not user:
        raise AuthError("Not logged in.")
    return user


def is_global_admin(user):
    return user.get("role") == "global_admin"


def is_household_admin(user, household):
    return is_global_admin(user) or household in user.get("admin_households", [])


def any_household_admin(user):
    return is_global_admin(user) or bool(user.get("admin_households"))


def require_global_admin(handler):
    user = require_user(handler)
    if not is_global_admin(user):
        raise AuthError("Global admin only.")
    return user


def require_any_household_admin(handler):
    user = require_user(handler)
    if not any_household_admin(user):
        raise AuthError("Household admin only.")
    return user


def allowed_household(user, household):
    return household in user.get("households", []) or is_global_admin(user)


def user_households(user):
    return sorted(set(user.get("households", [])))


def user_admin_households(user):
    if is_global_admin(user):
        return list_households()
    return sorted(set(user.get("admin_households", [])))


# ======================= households =======================

def household_dir(household):
    if not re.fullmatch(r"[a-z0-9åäö\-_]+", household):
        raise ValueError("Invalid household name.")
    return os.path.join(DATA_DIR, "households", household)


def list_households():
    base = os.path.join(DATA_DIR, "households")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))


def ensure_household(household):
    hdir = household_dir(household)
    os.makedirs(hdir, exist_ok=True)
    path = os.path.join(hdir, "inventory.csv")
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(INVENTORY_HEADER)
        return
    # migrate old inventory header if needed
    with open(path, newline="", encoding="utf-8") as f:
        current = next(csv.reader(f), None) or []
    if current != INVENTORY_HEADER:
        rows = [{h: r.get(h, "") for h in INVENTORY_HEADER}
                for r in csv.DictReader(open(path, newline="", encoding="utf-8"))]
        write_csv(path, INVENTORY_HEADER, rows)


def normalize_product_row(p):
    """Map a row from any older header (v2.0-v2.3) onto PRODUCTS_HEADER."""
    old = p.get("category", "")
    if any(t["id"] == old for t in get_food_types()):
        ftype, category = old, ""      # v2.3 type id -> type
    else:
        ftype, category = "", old      # free text -> keep as category
    return {"name": p.get("name", ""), "manufacturer": p.get("manufacturer", ""),
            "type": ftype, "category": category, "size": p.get("size", ""),
            "added_date": p.get("added_date", "")}


def migrate_products_csv():
    """v2.3 (category id) -> v2.4 (type + sub-category + size) header."""
    if not os.path.exists(PRODUCTS_CSV):
        return
    with open(PRODUCTS_CSV, newline="", encoding="utf-8") as f:
        current = next(csv.reader(f), None) or []
    if current == PRODUCTS_HEADER:
        return
    rows = [normalize_product_row(p)
            for p in csv.DictReader(open(PRODUCTS_CSV, newline="", encoding="utf-8"))]
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, rows)


def ensure_global_products():
    """Merge per-household / legacy flat products.csv into the global list.

    v2.4 keeps one shared product list at DATA_DIR/products.csv. Older
    versions stored it either flat at DATA_DIR/products.csv (v2.0-v2.3)
    or per household under households/<name>/products.csv (v2.2). Merge
    all sources into the global file (deduped on name+manufacturer),
    then remove the household copies.
    """
    if not os.path.exists(PRODUCTS_CSV):
        write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, [])
    merged = read_csv(PRODUCTS_CSV)
    seen = {(p.get("name", "").lower(), p.get("manufacturer", "").lower())
            for p in merged}
    sources = []
    old_flat = os.path.join(DATA_DIR, "products.csv")
    if os.path.abspath(old_flat) != os.path.abspath(PRODUCTS_CSV):
        sources.append(old_flat)
    hdir = os.path.join(DATA_DIR, "households")
    if os.path.isdir(hdir):
        for h in sorted(os.listdir(hdir)):
            sources.append(os.path.join(hdir, h, "products.csv"))
    for path in sources:
        if not os.path.exists(path):
            continue
        for p in read_csv(path):
            row = normalize_product_row(p)
            key = (row["name"].lower(), row["manufacturer"].lower())
            if key in seen or not key[0]:
                continue
            seen.add(key)
            merged.append(row)
        os.remove(path)
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, merged)


def seed_barcode_defaults():
    """v2.8: seed the bundled Swedish emergency-food barcode defaults.

    On first start (or when BARCODE_DEFAULTS_SEED changes): add any missing
    products from data/barcode-defaults.json to the global product list and
    map their barcodes. Never overwrites existing products or mappings, and
    runs only once per seed version — mappings deleted by an admin stay
    deleted.
    """
    cfg = get_config()
    if cfg.get("barcode_defaults_seed") == BARCODE_DEFAULTS_SEED:
        return
    try:
        with open(BARCODE_DEFAULTS_FILE, encoding="utf-8") as f:
            defaults = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        defaults = []
    if not isinstance(defaults, list):
        defaults = []
    type_ids = {t["id"] for t in get_food_types()}
    products = read_csv(PRODUCTS_CSV)
    seen = {(p.get("name", "").lower(), p.get("manufacturer", "").lower())
            for p in products}
    barcodes = cfg.setdefault("barcodes", {})
    added = mapped = 0
    for d in defaults:
        name = str(d.get("name", "")).strip()
        code = str(d.get("barcode", "")).strip()
        manufacturer = str(d.get("manufacturer", "")).strip()
        if not name or not code:
            continue
        key = (name.lower(), manufacturer.lower())
        if key not in seen:
            seen.add(key)
            ftype = d.get("type", "")
            products.append({
                "name": name,
                "manufacturer": manufacturer,
                "type": ftype if ftype in type_ids else "",
                "category": str(d.get("category", "")).strip(),
                "size": str(d.get("size", "")).strip(),
                "added_date": today().isoformat(),
            })
            added += 1
        if code not in barcodes:
            barcodes[code] = {"name": name, "manufacturer": manufacturer}
            mapped += 1
    if added:
        write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, products)
    cfg["barcode_defaults_seed"] = BARCODE_DEFAULTS_SEED
    save_json(CONFIG_FILE, cfg)
    if added or mapped:
        print(f"v2.8 barcode defaults seeded: {added} product(s) added, "
              f"{mapped} barcode(s) mapped")


# ======================= model =======================

def alert_level(best):
    days = (best - today()).days
    if days < 0:
        return "expired"
    if days <= ALERT_WINDOWS["1month"]:
        return "1month"
    if days <= ALERT_WINDOWS["3months"]:
        return "3months"
    if days <= ALERT_WINDOWS["6months"]:
        return "6months"
    return "ok"


def add_product(name, manufacturer, ftype, category, size):
    name = name.strip()
    manufacturer = (manufacturer or "").strip()
    ftype = (ftype or "").strip()
    category = (category or "").strip()
    size = (size or "").strip()
    if not name:
        raise ValueError("Product name is required.")
    for field in (name, manufacturer, category, size):
        if not valid_name(field):
            raise ValueError("Product fields contain invalid characters.")
    if ftype and not any(t["id"] == ftype for t in get_food_types()):
        raise ValueError("Unknown type.")
    products = read_csv(PRODUCTS_CSV)
    if any(p["name"].lower() == name.lower()
           and p.get("manufacturer", "").lower() == manufacturer.lower()
           for p in products):
        raise ValueError(f"'{name}' by '{manufacturer or 'unknown maker'}' is already on the list.")
    products.append({"name": name, "manufacturer": manufacturer, "type": ftype,
                     "category": category, "size": size,
                     "added_date": today().isoformat()})
    products.sort(key=lambda p: (p["name"].lower(), p.get("manufacturer", "").lower()))
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, products)


def update_product(old_name, old_manufacturer, name, manufacturer, ftype, category, size):
    """Update a product globally, updating all household inventories."""
    products = read_csv(PRODUCTS_CSV)
    old_key = (old_name.strip().lower(), (old_manufacturer or "").strip().lower())
    match = next((p for p in products
                  if (p["name"].lower(), p.get("manufacturer", "").lower()) == old_key), None)
    if not match:
        raise ValueError("Product not found.")
    name = name.strip()
    manufacturer = (manufacturer or "").strip()
    ftype = (ftype or "").strip()
    category = (category or "").strip()
    size = (size or "").strip()
    if not name:
        raise ValueError("Product name is required.")
    for field in (name, manufacturer, category, size):
        if not valid_name(field):
            raise ValueError("Product fields contain invalid characters.")
    if ftype and not any(t["id"] == ftype for t in get_food_types()):
        raise ValueError("Unknown type.")
    new_key = (name.lower(), manufacturer.lower())
    if new_key != old_key and any((p["name"].lower(), p.get("manufacturer", "").lower()) == new_key
                                  for p in products):
        raise ValueError(f"'{name}' by '{manufacturer or 'unknown maker'}' already exists.")
    match.update({"name": name, "manufacturer": manufacturer, "type": ftype,
                  "category": category, "size": size})
    products.sort(key=lambda p: (p["name"].lower(), p.get("manufacturer", "").lower()))
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, products)
    # update references in every household inventory
    for hh in list_households():
        path = os.path.join(household_dir(hh), "inventory.csv")
        rows = read_csv(path)
        dirty = False
        for r in rows:
            if (r["product"].lower(), r.get("manufacturer", "").lower()) == old_key:
                r["product"], r["manufacturer"] = name, manufacturer
                dirty = True
        if dirty:
            write_csv(path, INVENTORY_HEADER, rows)


def remove_product(name, manufacturer=None):
    products = read_csv(PRODUCTS_CSV)
    name_l, man_l = name.lower(), (manufacturer or "").lower()
    matching = [p for p in products
                if p["name"].lower() == name_l
                and (manufacturer is None or p.get("manufacturer", "").lower() == man_l)]
    if not matching:
        raise ValueError("Product not found.")
    keep = {(p["name"].lower(), p.get("manufacturer", "").lower()) for p in matching}
    for hh in list_households():
        inv = read_csv(os.path.join(household_dir(hh), "inventory.csv"))
        if any((r["product"].lower(), r.get("manufacturer", "").lower()) in keep for r in inv):
            raise ValueError("Product still has items in an inventory; remove them first.")
    write_csv(PRODUCTS_CSV, PRODUCTS_HEADER,
              [p for p in products
               if (p["name"].lower(), p.get("manufacturer", "").lower()) not in keep])


def buy(household, product, manufacturer, best_before, quantity):
    ensure_household(household)
    inv_path = os.path.join(household_dir(household), "inventory.csv")
    product, manufacturer = product.strip(), (manufacturer or "").strip()
    if not any(p["name"].lower() == product.lower()
               and p.get("manufacturer", "").lower() == manufacturer.lower()
               for p in read_csv(PRODUCTS_CSV)):
        raise ValueError(f"Unknown product '{product}'. Add it to the list first.")
    try:
        best = parse_date(best_before)
    except ValueError:
        raise ValueError("Invalid date. Use YYYY-MM-DD.")
    if best < today():
        raise ValueError("Best-before date is in the past.")
    quantity = max(1, int(quantity))
    inv = read_csv(inv_path)
    inv.append({"id": str(max((int(r["id"]) for r in inv), default=0) + 1),
                "product": product, "manufacturer": manufacturer,
                "best_before": best.isoformat(),
                "quantity": str(quantity), "added_date": today().isoformat()})
    write_csv(inv_path, INVENTORY_HEADER, inv)


def remove_item(household, item_id):
    ensure_household(household)
    inv_path = os.path.join(household_dir(household), "inventory.csv")
    inv = read_csv(inv_path)
    remaining = [r for r in inv if r["id"] != str(item_id)]
    if len(remaining) == len(inv):
        raise ValueError("Item not found.")
    write_csv(inv_path, INVENTORY_HEADER, remaining)


def update_quantity(household, item_id, quantity):
    """Change the quantity of an existing inventory item."""
    ensure_household(household)
    inv_path = os.path.join(household_dir(household), "inventory.csv")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a whole number.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1. Use the ✕ button to remove an item.")
    inv = read_csv(inv_path)
    for r in inv:
        if r["id"] == str(item_id):
            r["quantity"] = str(quantity)
            write_csv(inv_path, INVENTORY_HEADER, inv)
            return
    raise ValueError("Item not found.")


def migrate_items(from_hh, to_hh, item_ids=None):
    """Move all (or selected) inventory items from one household to another."""
    ensure_household(from_hh)
    ensure_household(to_hh)
    src = os.path.join(household_dir(from_hh), "inventory.csv")
    dst = os.path.join(household_dir(to_hh), "inventory.csv")
    rows = read_csv(src)
    if not rows:
        raise ValueError(f"Household '{from_hh}' has no inventory items.")
    if item_ids:
        wanted = {str(i) for i in item_ids}
        moving = [r for r in rows if r["id"] in wanted]
        if not moving:
            raise ValueError("No matching items to migrate.")
    else:
        moving = rows
    keep = [r for r in rows if r not in moving]
    target = read_csv(dst)
    next_id = max((int(r["id"]) for r in target), default=0)
    for r in moving:
        next_id += 1
        target.append({**r, "id": str(next_id)})
    write_csv(dst, INVENTORY_HEADER, target)
    write_csv(src, INVENTORY_HEADER, keep)
    return len(moving)


def inventory_view(household):
    ensure_household(household)
    # v2.5: join each item with its product's type/category/size
    products = {}
    for p in read_csv(PRODUCTS_CSV):
        products[(p["name"].lower(), p.get("manufacturer", "").lower())] = p
    rows = []
    for r in read_csv(os.path.join(household_dir(household), "inventory.csv")):
        best = parse_date(r["best_before"])
        days = (best - today()).days
        p = products.get((r["product"].lower(), r.get("manufacturer", "").lower()), {})
        rows.append({"id": int(r["id"]), "product": r["product"],
                     "manufacturer": r.get("manufacturer", ""),
                     "type": p.get("type", ""), "category": p.get("category", ""),
                     "size": p.get("size", ""),
                     "best_before": r["best_before"], "quantity": int(r["quantity"]),
                     "days_left": days, "level": alert_level(best)})
    rows.sort(key=lambda r: r["days_left"])
    return rows


def products_view():
    return read_csv(PRODUCTS_CSV)


# ======================= HTTP =======================

def send_redirect(handler, location, set_cookie=None):
    handler.send_response(302)
    handler.send_header("Location", location)
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def widget_response(households):
    """Aggregated widget data across the given households.
    Warning buckets are exclusive. total_items = total quantity (units)."""
    households = [h for h in households if h]
    entries = 0
    quantities = 0
    counts = {"expired": 0, "1month": 0, "3months": 0, "6months": 0, "ok": 0}
    expiring = []
    per_household = {}
    for hh in households:
        hh_entries = 0
        hh_qty = 0
        hh_attention = 0
        for r in inventory_view(hh):
            counts[r["level"]] += 1
            entries += 1
            hh_entries += 1
            quantities += r["quantity"]
            hh_qty += r["quantity"]
            if r["level"] != "ok":
                hh_attention += 1
                expiring.append({**r, "household": hh})
        per_household[hh] = {"total_items": hh_qty, "total_entries": hh_entries,
                             "attention": hh_attention}
    expiring.sort(key=lambda r: r["days_left"])
    return {
        "households": households,
        "total_items": quantities,
        "total_quantity": quantities,
        "total_entries": entries,
        "expiring_within_1_month": counts["1month"],
        "expiring_within_3_months": counts["3months"],
        "expiring_within_6_months": counts["6months"],
        "expired": counts["expired"],
        "attention": counts["1month"] + counts["3months"] + counts["6months"] + counts["expired"],
        "per_household": per_household,
        "next_expiries": [{k: r[k] for k in ("household", "product", "manufacturer",
                                             "best_before", "days_left", "level")}
                          for r in expiring[:10]],
        "alerts": [f"[{r['household']}] {r['product']}: "
                   + ("EXPIRED" if r["level"] == "expired" else f"{r['days_left']} days left")
                   + f" (best before {r['best_before']})"
                   for r in expiring[:10]],
    }


def user_public(user):
    return {"username": user["username"],
            "role": user.get("role", "user"),
            "is_admin": is_global_admin(user),          # convenience for the UI
            "households": user.get("households", []),
            "admin_households": user.get("admin_households", []),
            "email": user.get("email", ""),
            "oidc": bool(user.get("oidc_sub"))}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def reply(self, code, body, content_type="application/json", set_cookie=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def session_cookie(self, token, clear=False):
        if clear:
            return "session=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax"
        return f"session={token}; HttpOnly; Path=/; Max-Age={SESSION_TTL}; SameSite=Lax"

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body.")

    def household_of(self, user, body=None):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        household = (body or {}).get("household") or qs.get("household", [None])[0]
        if not household:
            # v2.5: no implicit 'default' household — fall back to the
            # user's own first household instead.
            household = (user.get("households") or [None])[0]
        if not household:
            raise ValueError("You are not assigned to any household yet.")
        if not allowed_household(user, household):
            raise AuthError(f"No access to household '{household}'.")
        return household

    # ---------------- GET ----------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                    self.reply(200, f.read(), "text/html; charset=utf-8")
            elif path == "/app-version.txt":
                # v2.7.4: current bundled app version (for the download link)
                try:
                    with open(os.path.join(APP_DIR, "app", "app-version.txt"),
                              "r", encoding="utf-8") as f:
                        self.reply(200, f.read().strip().encode("utf-8"),
                                   "text/plain; charset=utf-8")
                except FileNotFoundError:
                    self.reply(404, {"error": "app version unknown"})
            elif re.fullmatch(r"/app(?:-[\w.]+)?\.apk", path):
                # v2.7: serve the bundled Android app (stored base64 in the
                # repo so it survives text-only pushes; decoded once, cached).
                # v2.7.4: also answers versioned paths like /app-2.7.3.apk —
                # a unique URL per app version, which no cache (browser,
                # Cloudflare, proxy) can serve stale.
                global APP_APK_BYTES
                try:
                    if APP_APK_BYTES is None:
                        with open(APP_APK_B64, "r", encoding="utf-8") as f:
                            APP_APK_BYTES = base64.b64decode("".join(f.read().split()))
                except FileNotFoundError:
                    self.reply(404, {"error": "app.apk not bundled"})
                    return
                self.send_response(200)
                self.send_header("Content-Type",
                                  "application/vnd.android.package-archive")
                # v2.7.3: version in the filename so a stale download is
                # instantly recognisable on the phone.
                try:
                    with open(os.path.join(APP_DIR, "app", "app-version.txt"),
                              "r", encoding="utf-8") as f:
                        app_ver = f.read().strip() or "dev"
                except FileNotFoundError:
                    app_ver = "dev"
                self.send_header("Content-Disposition",
                                 f'attachment; filename="emergency-food-tracker-{app_ver}.apk"')
                self.send_header("Content-Length", str(len(APP_APK_BYTES)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(APP_APK_BYTES)
            elif path == "/api/barcode":
                # v2.7: barcode lookup for the app's scan feature
                user = require_user(self)
                code = (qs.get("code", [""])[0] or "").strip()
                hit = get_config().get("barcodes", {}).get(code)
                if hit:
                    prod = next((p for p in read_csv(PRODUCTS_CSV)
                                 if p["name"].lower() == hit.get("name", "").lower()
                                 and p.get("manufacturer", "").lower()
                                 == hit.get("manufacturer", "").lower()), None)
                    self.reply(200, {"found": True, "product": prod})
                else:
                    self.reply(200, {"found": False})
            elif path == "/api/bootstrap":
                user = current_user(self)
                get_config()
                self.reply(200, {
                    "configured": user_count() > 0,
                    "oidc_enabled": oidc_enabled(),
                    "password_login": password_login_enabled(),
                    "oidc_name": get_config()["oidc"].get("name") or "SSO",
                    "version": "2.8.0",
                    "user": ({**user_public(user),
                              "api_key": user.get("api_key", ""),
                              "visible_households": user_households(user) if not is_global_admin(user)
                              else list_households()} if user else None),
                })
            elif path == "/api/data":
                user = require_user(self)
                h = self.household_of(user)
                self.reply(200, {"products": products_view(),
                                 "inventory": inventory_view(h),
                                 "types": get_food_types(),
                                 "today": today().isoformat(),
                                 "household": h,
                                 "households": list_households()})
            elif path == "/api/oidc/login":
                if not oidc_enabled():
                    raise ValueError("OIDC is not configured.")
                oidc = get_config()["oidc"]
                eps = oidc_discovery(oidc)
                state = secrets.token_urlsafe(16)
                SESSIONS["oidc-state-" + state] = {"expires": now() + 600}
                base = oidc.get("redirect_uri") or f"http://{self.headers.get('Host', 'localhost')}/api/oidc/callback"
                params = urllib.parse.urlencode({
                    "response_type": "code",
                    "client_id": oidc["client_id"],
                    "redirect_uri": base,
                    "scope": oidc.get("scopes") or "openid profile email",
                    "state": state,
                })
                send_redirect(self, eps["authorize"] + "?" + params)
            elif path == "/api/oidc/callback":
                self.oidc_callback(qs)
            # ---------- users / roles listings ----------
            elif path == "/api/admin/users":
                user = require_user(self)
                if is_global_admin(user):
                    visible = get_users()["users"]
                elif user.get("admin_households"):
                    mine = set(user["admin_households"])
                    visible = [u for u in get_users()["users"]
                               if mine & set(u.get("households", []))]
                else:
                    raise AuthError("Household admin only.")
                self.reply(200, {"users": [user_public(u) for u in visible],
                                 "viewer_role": user.get("role"),
                                 "viewer_admin_households": user_admin_households(user),
                                 "all_households": list_households()})
            elif path == "/api/admin/households":
                user = require_user(self)
                if is_global_admin(user):
                    households = list_households()
                else:
                    households = [h for h in user_households(user) if h in list_households()]
                self.reply(200, {"households": households})
            elif path == "/api/admin/config":
                require_global_admin(self)
                oidc = get_config()["oidc"]
                cfg = get_config()
                self.reply(200, {"oidc": {k: oidc.get(k, "")
                                          for k in ("name", "issuer", "client_id", "client_secret",
                                                    "redirect_uri", "scopes", "admin_emails")},
                                 "oidc_auto_create": oidc.get("auto_create", True),
                                 "oidc_configured": oidc_configured(),
                                 "oidc_enabled": oidc_enabled(),
                                 "password_login": password_login_enabled(),
                                 "auth": cfg.get("auth", {}),
                                 "types": get_food_types(),
                                 "default_types": DEFAULT_FOOD_TYPES})
            elif path == "/api/admin/barcodes":
                # v2.7: list barcode -> product mappings
                require_global_admin(self)
                bc = get_config().get("barcodes", {})
                self.reply(200, {"barcodes": [
                    {"barcode": code, "name": v.get("name", ""),
                     "manufacturer": v.get("manufacturer", "")}
                    for code, v in bc.items()]})
            # ---------- homepage widget ----------
            elif path == "/api/widget":
                key = qs.get("key", [""])[0]
                owner = find_user_by_api_key(key)
                if not owner:
                    self.reply(401, {"error": "invalid key"})
                    return
                raw = qs.get("household", ["all"])[0] or "all"
                all_hh = list_households()
                if is_global_admin(owner):
                    accessible = all_hh
                else:
                    accessible = [h for h in owner.get("households", []) if h in all_hh]
                if raw.lower() in ("all", "*"):
                    households = accessible
                else:
                    wanted = [slugify(h) for h in raw.split(",") if h.strip()]
                    households = [h for h in wanted if h in accessible]
                    unknown = [h for h in wanted if h not in accessible]
                    if not households or unknown:
                        raise ValueError(f"Unknown or forbidden household(s): "
                                         f"{', '.join(unknown) or '(none)'}")
                self.reply(200, widget_response(households))
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except ValueError as e:
            self.reply(400, {"error": str(e)})

    def oidc_callback(self, qs):
        oidc = get_config()["oidc"]
        state = qs.get("state", [""])[0]
        if not state or "oidc-state-" + state not in SESSIONS:
            raise ValueError("Invalid OIDC state.")
        SESSIONS.pop("oidc-state-" + state, None)
        code = qs.get("code", [""])[0]
        if not code:
            raise ValueError("No code from OIDC provider.")
        eps = oidc_discovery(oidc)
        base = oidc.get("redirect_uri") or f"http://{self.headers.get('Host', 'localhost')}/api/oidc/callback"
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code", "code": code, "redirect_uri": base,
            "client_id": oidc["client_id"], "client_secret": oidc.get("client_secret", ""),
        }).encode()
        req = urllib.request.Request(eps["token"], data=data,
                                     headers={**OIDC_HTTP_HEADERS,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as r:
            tok = json.loads(r.read().decode())
        req2 = urllib.request.Request(eps["userinfo"],
                                      headers={**OIDC_HTTP_HEADERS,
                                               "Authorization": "Bearer " + tok["access_token"]})
        with urllib.request.urlopen(req2, timeout=10) as r:
            info = json.loads(r.read().decode())
        username = info.get("preferred_username") or info.get("email") or info.get("sub", "")
        email = info.get("email", "")
        user = find_user(username)
        if not user and email:
            user = next((u for u in get_users()["users"]
                         if (u.get("email") or "").lower() == email.lower()), None)
        if not user:
            if oidc.get("auto_create") is False:
                raise ValueError("OIDC user not known; ask an admin to create your account.")
            is_admin = email in (oidc.get("admin_emails") or [])
            role = "global_admin" if is_admin else "user"
            households = list_households()[:1]
            if role == "user" and not households:
                raise ValueError("No household exists yet; ask an admin to create one first.")
            create_user(username, "", role=role, households=households,
                        admin_households=households if role == "user" else [],
                        oidc_sub=info.get("sub"), email=email)
            user = find_user(username)
        token = create_session(user["username"])
        send_redirect(self, "/", self.session_cookie(token))

    # ---------------- POST ----------------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            body = self.read_body()
            if path == "/api/setup":
                if user_count() > 0:
                    raise ValueError("Setup already done.")
                if not body.get("username") or not body.get("password"):
                    raise ValueError("Username and password required.")
                hh = slugify(body.get("household") or "")
                if not hh:
                    raise ValueError("Please name your first household.")
                ensure_household(hh)
                create_user(body["username"], body["password"], role="global_admin",
                            households=[hh])
                token = create_session(body["username"].strip())
                self.reply(200, {"ok": True}, set_cookie=self.session_cookie(token))
            elif path == "/api/login":
                if not password_login_enabled():
                    raise ValueError("Password login is disabled. Please use SSO.")
                user = find_user(body.get("username", ""))
                if not user or not user.get("password") or not check_password(user, body.get("password", "")):
                    raise ValueError("Wrong username or password.")
                token = create_session(user["username"])
                self.reply(200, {"ok": True}, set_cookie=self.session_cookie(token))
            elif path == "/api/logout":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                if cookie.get("session"):
                    SESSIONS.pop(cookie["session"].value, None)
                self.reply(200, {"ok": True}, set_cookie=self.session_cookie("", clear=True))
            # -------- products (global; household admins & up) --------
            elif path == "/api/products":
                require_any_household_admin(self)
                add_product(body.get("name", ""), body.get("manufacturer", ""),
                            body.get("type", ""), body.get("category", ""),
                            body.get("size", ""))
                self.reply(201, {"ok": True})
            elif path == "/api/buy":
                user = require_user(self)
                buy(self.household_of(user, body), body.get("product", ""),
                    body.get("manufacturer", ""), body.get("best_before", ""),
                    body.get("quantity", 1))
                self.reply(201, {"ok": True})
            # -------- me --------
            elif path == "/api/me/apikey":
                user = require_user(self)
                users = get_users()
                target = next(u for u in users["users"]
                              if u["username"] == user["username"])
                target["api_key"] = secrets.token_urlsafe(24)
                save_users(users)
                self.reply(200, {"ok": True, "api_key": target["api_key"]})
            # -------- users / households admin --------
            elif path == "/api/admin/users":
                requester = require_user(self)
                if not body.get("username") or not body.get("password"):
                    raise ValueError("Username and password required.")
                households = [slugify(h) for h in body.get("households", []) if slugify(h)]
                if not households:
                    raise ValueError("A new user needs at least one household.")
                for hh in households:
                    ensure_household(hh)
                if is_global_admin(requester):
                    role = "global_admin" if body.get("role") == "global_admin" else "user"
                    admin_hh = [h for h in (body.get("admin_households") or []) if h in households]
                elif requester.get("admin_households"):
                    role = "user"
                    admin_hh = [h for h in households if h in requester["admin_households"]]
                    if not set(households) <= set(requester["admin_households"]):
                        raise AuthError("You can only create users in households you admin.")
                else:
                    raise AuthError("Household admin only.")
                create_user(body["username"], body["password"], role=role,
                            households=households,
                            admin_households=admin_hh if role == "user" else [])
                self.reply(201, {"ok": True})
            elif path == "/api/admin/households":
                # Any logged-in user may create a household and becomes its
                # household admin. Global admins may assign other users too.
                user = require_user(self)
                hh = slugify(body.get("name", ""))
                if not hh:
                    raise ValueError("Please give the household a name.")
                if hh in list_households():
                    raise ValueError(f"Household '{hh}' already exists.")
                ensure_household(hh)
                users = get_users()
                me = next(u for u in users["users"] if u["username"] == user["username"])
                if hh not in me.get("households", []):
                    me.setdefault("households", []).append(hh)
                if me.get("role") != "global_admin" and hh not in me.get("admin_households", []):
                    me.setdefault("admin_households", []).append(hh)
                assigned = []
                for uname in body.get("users", []) or []:
                    target = next((u for u in users["users"]
                                   if u["username"].lower() == str(uname).lower()), None)
                    if target:
                        if hh not in target.get("households", []):
                            target.setdefault("households", []).append(hh)
                        assigned.append(target["username"])
                save_users(users)
                self.reply(201, {"ok": True, "household": hh, "assigned": assigned})
            elif path == "/api/admin/migrate":
                user = require_user(self)
                frm = slugify(body.get("from", ""))
                to = slugify(body.get("to", ""))
                if frm == to:
                    raise ValueError("Source and target household must differ.")
                if not is_household_admin(user, frm):
                    raise AuthError("You are not the admin of the source household.")
                moved = migrate_items(frm, to, body.get("item_ids"))
                self.reply(200, {"ok": True, "moved": moved})
            elif path == "/api/admin/barcodes":
                # v2.7: map (or re-map) a scanned barcode to a global product
                require_global_admin(self)
                code = str(body.get("barcode", "")).strip()
                name = str(body.get("name", "")).strip()
                manufacturer = str(body.get("manufacturer", "")).strip()
                if not code:
                    raise ValueError("Please provide a barcode.")
                prod = next((p for p in read_csv(PRODUCTS_CSV)
                             if p["name"].lower() == name.lower()
                             and p.get("manufacturer", "").lower()
                             == manufacturer.lower()), None)
                if not prod:
                    raise ValueError("Unknown product. Add it to the product "
                                     "list first.")
                cfg = get_config()
                cfg.setdefault("barcodes", {})[code] = {
                    "name": prod["name"], "manufacturer": prod.get("manufacturer", "")}
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True, "barcode": code, "name": prod["name"]})
            elif path == "/api/admin/oidc":
                require_global_admin(self)
                cfg = get_config()
                oidc = cfg["oidc"]
                for k in ("name", "issuer", "client_id", "client_secret", "redirect_uri", "scopes"):
                    if k in body:
                        oidc[k] = str(body[k]).strip()
                if "auto_create" in body:
                    oidc["auto_create"] = bool(body["auto_create"])
                if isinstance(body.get("admin_emails"), list):
                    oidc["admin_emails"] = [str(e).strip() for e in body["admin_emails"]]
                # v2.5 auth toggles
                if "sso_login" in body:
                    cfg["auth"]["sso_login"] = bool(body["sso_login"])
                if "password_login" in body:
                    want_off = not bool(body["password_login"])
                    # only honoured while SSO is configured and enabled,
                    # so an instance can never lock itself out.
                    if want_off and not (oidc.get("issuer") and oidc.get("client_id")
                                         and cfg["auth"].get("sso_login", True)):
                        raise ValueError("Password login can only be disabled when "
                                         "SSO is configured and enabled.")
                    cfg["auth"]["password_login"] = not want_off
                oidc.pop("endpoints", None)
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True, "oidc_enabled": oidc_enabled(),
                                 "password_login": password_login_enabled()})
            elif path == "/api/admin/types":
                # v2.5: global admins may customise the type/category options
                require_global_admin(self)
                types_in = body.get("types")
                if not isinstance(types_in, list) or not types_in:
                    raise ValueError("types must be a non-empty list.")
                clean = []
                seen_ids = set()
                for t in types_in:
                    if not isinstance(t, dict):
                        raise ValueError("Each type must be an object.")
                    tid = slugify(t.get("id", ""))
                    label = str(t.get("label", "")).strip()
                    cats = t.get("categories")
                    if not tid or tid in seen_ids:
                        raise ValueError("Each type needs a unique id.")
                    seen_ids.add(tid)
                    if not label or not valid_label(label):
                        raise ValueError(f"Invalid label for type '{tid}'.")
                    if cats is None:
                        cats = []
                    if not isinstance(cats, list):
                        raise ValueError(f"categories for '{tid}' must be a list.")
                    cats = [str(c).strip() for c in cats if str(c).strip()]
                    for c in cats:
                        if not valid_label(c):
                            raise ValueError(f"Invalid category '{c}' in '{tid}'.")
                    months = t.get("shelf_life_months", [12, 36])
                    if (not isinstance(months, list) or len(months) != 2
                            or not all(isinstance(m, int) and m > 0 for m in months)):
                        months = [12, 36]
                    clean.append({"id": tid, "label": label,
                                  "storage": t.get("storage") or "pantry",
                                  "shelf_life_months": months,
                                  "categories": cats})
                cfg = get_config()
                cfg["food_types"] = clean
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True, "types": clean})
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})

    # ---------------- PUT ----------------
    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            body = self.read_body()
            m = re.fullmatch(r"/api/inventory/(\d+)", path)
            if m:
                user = require_user(self)
                update_quantity(self.household_of(user, body), m.group(1),
                                body.get("quantity"))
                self.reply(200, {"ok": True})
                return
            if path == "/api/products":
                require_any_household_admin(self)
                update_product(body.get("old_name", ""), body.get("old_manufacturer", ""),
                               body.get("name", ""), body.get("manufacturer", ""),
                               body.get("type", ""), body.get("category", ""),
                               body.get("size", ""))
                self.reply(200, {"ok": True})
            elif path == "/api/admin/users":
                requester = require_user(self)
                uname = body.get("username", "")
                users = get_users()
                target = next((u for u in users["users"]
                               if u["username"].lower() == uname.lower()), None)
                if not target:
                    raise ValueError("User not found.")
                if is_global_admin(requester):
                    if "role" in body:
                        if body["role"] not in ("user", "global_admin"):
                            raise ValueError("Invalid role.")
                        target["role"] = body["role"]
                    if isinstance(body.get("households"), list):
                        households = [slugify(h) for h in body["households"] if slugify(h)]
                        if not households and target["role"] != "global_admin":
                            raise ValueError("A user needs at least one household.")
                        for hh in households:
                            ensure_household(hh)
                        target["households"] = households
                        target["admin_households"] = [h for h in target.get("admin_households", [])
                                                      if h in households]
                    if isinstance(body.get("admin_households"), list):
                        target["admin_households"] = [h for h in body["admin_households"]
                                                      if h in target.get("households", [])]
                    if body.get("password"):
                        if len(body["password"]) < 8:
                            raise ValueError("Password must be at least 8 characters.")
                        salt, ph = hash_password(body["password"])
                        target["password"] = f"{salt}${ph}"
                elif requester.get("admin_households"):
                    mine = set(requester["admin_households"])
                    # household admin: manage users within their households only
                    if isinstance(body.get("households"), list):
                        wanted = [slugify(h) for h in body["households"] if slugify(h)]
                        current = set(target.get("households", []))
                        additions = [h for h in wanted if h not in current and h in mine]
                        removals = [h for h in current - set(wanted) if h in mine]
                        hh_set = (current - set(removals)) | set(additions)
                        target["households"] = sorted(hh_set)
                        target["admin_households"] = [h for h in target.get("admin_households", [])
                                                      if h in hh_set]
                        for hh in additions:
                            ensure_household(hh)
                    if isinstance(body.get("admin_households"), list):
                        wanted = set(body["admin_households"]) & mine & set(target.get("households", []))
                        target["admin_households"] = sorted(
                            (set(target.get("admin_households", [])) - mine) | wanted)
                    if body.get("password"):
                        if len(body["password"]) < 8:
                            raise ValueError("Password must be at least 8 characters.")
                        salt, ph = hash_password(body["password"])
                        target["password"] = f"{salt}${ph}"
                else:
                    raise AuthError("Household admin only.")
                save_users(users)
                self.reply(200, {"ok": True})
            elif re.fullmatch(r"/api/admin/households/([^/]+)", path):
                # v2.5: edit household membership (add/remove assigned users)
                user = require_user(self)
                hh = urllib.parse.unquote(re.fullmatch(
                    r"/api/admin/households/([^/]+)", path).group(1))
                if hh not in list_households():
                    raise ValueError("Household not found.")
                if not is_household_admin(user, hh):
                    raise AuthError("You are not the admin of this household.")
                if not isinstance(body.get("users"), list):
                    raise ValueError("users must be a list.")
                users = get_users()
                wanted = {u.lower() for u in body["users"] if str(u).strip()}
                changed = 0
                for u in users["users"]:
                    member = hh in u.get("households", [])
                    should = u["username"].lower() in wanted
                    if should and not member:
                        u.setdefault("households", []).append(hh)
                        changed += 1
                    elif member and not should:
                        u["households"] = [x for x in u["households"] if x != hh]
                        u["admin_households"] = [x for x in u.get("admin_households", [])
                                                 if x != hh]
                        changed += 1
                save_users(users)
                self.reply(200, {"ok": True, "changed": changed})
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})

    # ---------------- DELETE ----------------
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            user = require_user(self)
            m = re.fullmatch(r"/api/inventory/(\d+)", path)
            if m:
                h = self.household_of(user)
                remove_item(h, m.group(1))
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/products/(.+)", path)
            if m:
                require_any_household_admin(self)
                remove_product(urllib.parse.unquote(m.group(1)),
                               qs.get("manufacturer", [None])[0])
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/admin/users/(.+)", path)
            if m:
                require_global_admin(self)
                uname = urllib.parse.unquote(m.group(1))
                if uname.lower() == user["username"].lower():
                    raise ValueError("You cannot delete your own account.")
                users = get_users()
                remaining = [u for u in users["users"] if u["username"].lower() != uname.lower()]
                if len(remaining) == len(users["users"]):
                    raise ValueError("User not found.")
                users["users"] = remaining
                save_users(users)
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/admin/households/([^/]+)", path)
            if m:
                require_global_admin(self)
                hh = m.group(1)
                users = get_users()
                for u in users["users"]:
                    if hh in u.get("households", []):
                        u["households"] = [x for x in u["households"] if x != hh]
                        u["admin_households"] = [x for x in u.get("admin_households", [])
                                                 if x != hh]
                save_users(users)
                import shutil
                shutil.rmtree(household_dir(hh), ignore_errors=True)
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/admin/barcodes/([^/]+)", path)
            if m:
                # v2.7: remove a barcode mapping
                require_global_admin(self)
                code = urllib.parse.unquote(m.group(1))
                cfg = get_config()
                if code not in cfg.get("barcodes", {}):
                    raise ValueError("Barcode not found.")
                del cfg["barcodes"][code]
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True})
                return
            self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # migrate pre-2.2 flat inventory.csv into households/default/
    # (products.csv stays global and is merged by ensure_global_products)
    old_inv = os.path.join(DATA_DIR, "inventory.csv")
    if os.path.exists(old_inv):
        ensure_household("default")
        new = os.path.join(household_dir("default"), "inventory.csv")
        os.makedirs(os.path.dirname(new), exist_ok=True)
        if os.path.exists(new):
            os.remove(old_inv)
        else:
            os.replace(old_inv, new)
    # v2.3 category column -> v2.4 type/category/size columns
    migrate_products_csv()
    # v2.4: the product list is global again; merge any per-household
    # products.csv (and the old flat-layout copy) back into it.
    ensure_global_products()
    if not os.path.exists(PRODUCTS_CSV):
        write_csv(PRODUCTS_CSV, PRODUCTS_HEADER, [])
    # v2.8: seed the bundled Swedish emergency-food barcode defaults
    seed_barcode_defaults()
    get_users()   # normalizes roles + generates per-user API keys
    get_config()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Food storage tracker v2.8.0: http://0.0.0.0:{PORT} "
          f"(data: {DATA_DIR}, config: {CONFIG_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()

