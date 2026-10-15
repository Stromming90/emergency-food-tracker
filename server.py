#!/usr/bin/env python3
"""
Emergency Food Storage Tracker — Web UI server (v2.12.7)
=====================================================
Zero-dependency web server (Python stdlib only).

v2.12.7:
- Android app 2.12.6: a background check now also runs IMMEDIATELY
   every time the app is opened (new EFTNative.pollNow() called by
   the web UI at startup), so the Settings -> Notifications status
   refreshes right away instead of waiting up to 30 minutes. This
   also clears the "Last check: HTTP 401" state (a poll that ran
   while the session had expired) — after re-login the next app
   open re-polls with the fresh cookie.
- The test-notification button and pollNow post their work to the
   main thread and report every failure with a visible toast (plus
   the crash log), so nothing fails silently anymore.
v2.12.6:
- Android app 2.12.5: the last missing permission. JobScheduler
   requires ACCESS_NETWORK_STATE for jobs with a connectivity
   constraint — without it the schedule throws SecurityException
   (the reported Android 16 crash) and no background notification
   job ever exists. Added to the manifest; the job now schedules.
   The update dialog's browser buttons also changed: the intent://
   anchor-click trick did nothing in that device's WebView, so the
   page now calls EFTNative.openUrl (native ACTION_VIEW outside the
   WebView, with a visible toast on failure); the intent:// path
   remains only as a fallback for older apps.

v2.12.5:
- Android app 2.12.4: the in-app update download actually works.
   The system DownloadManager path silently failed on a real device
   (Android 16): tapping Download did nothing. The app now downloads
   /app.apk itself with HttpURLConnection into its own storage and
   hands the file straight to the package installer through a tiny
   bundled content provider (APKProvider), with REQUEST_INSTALL_PACKAGES
   declared so the system can prompt for it. The outcome (bytes or
   error) is toasted, recorded and shown in Settings -> Notifications.
   The web update dialog now appears for ALL app versions, offering
   "Download in app" (2.12.4+) plus Chrome / browser fallback buttons
   that cannot fail silently. Server code unchanged (version bump).

v2.12.4:
- Android app 2.12.3: native notifications now actually start. The
   manifest was missing RECEIVE_BOOT_COMPLETED, which JobScheduler
   requires for persisted jobs — so the background check was never
   scheduled (in app 2.12.0 the same exception was uncaught, which
   was the original "app closes on open" crash; 2.12.2 swallowed it,
   leaving notifications silently dead). Permission added, scheduling
   failures are now surfaced with a toast, and the app exposes an
   EFTNative bridge: the Settings -> Notifications tab shows the real
   status (permission, scheduled job, last background check) and has
   "Test native notification" and "Open notification settings"
   buttons. Server code unchanged apart from the Notifications UI.

v2.12.3:
- Android app 2.12.2: fixes the crash loop reported on a real phone.
   The background poll job (PollJobService) read the WebView session
   cookie from its worker thread; on some devices that throws an
   Error (not an Exception), which escaped the catch block and killed
   the whole app process — because the job is persisted, Android
   re-delivered it the moment the app process started, so the app
   closed immediately and could not be opened again (a reinstall does
   not clear the persisted job, matching the report exactly). The
   cookie is now read on the main thread inside onStartJob, and the
   whole job catches Throwable everywhere so it can never kill the
   process again. The app also records any uncaught exception and
   shows it on the next launch with a Copy button, so future crashes
   can be reported from the phone without USB debugging. Server code
   is unchanged (version bump only).

v2.12.2:
- Fix: on the old app (v2.12.0, which has no download handler), the
   "Download update" button silently did nothing on devices where the
   bare intent:// escape URL was swallowed. It now opens a guided
   "Get the app update" dialog: buttons that open the APK download in
   Chrome (explicit package) or the default browser via a real anchor
   click (more reliable in old WebViews), plus the server address
   spelled out for a manual browser visit. New apps (2.12.1+) and
   plain browsers still download directly. UI/server only — the APK
   is unchanged (still 2.12.1).

v2.12.1:
- Android app discoverability & updates: the web UI now has a
  Settings -> About tab with the APK download, a dismissible
  "Get the Android app" banner for Android browsers, and — inside
  the app — an automatic update check that compares the app's
  EFT-Android/<version> user-agent token against app/app-version.txt
  and shows a "Download update" banner. The app (v2.12.1+) downloads
  the update in-app via the system DownloadManager; the older
  v2.12.0 app is bounced through the browser with an intent:// URL.

v2.12.0:
- Native push notifications for the Android APK app itself: the app
  now runs a periodic background job (about every 30 minutes) that
  polls GET /api/push/inbox?device=<uuid> with the app's session
  cookie and raises a real system notification when an item's status
  tag worsens — even when the app is closed. No third-party apps, no
  accounts: the device auto-registers on first poll, each successful
  poll refreshes the login session (sliding expiry), and devices
  that have not polled in 90 days are pruned. The first poll only
  establishes the baseline. The browser Web Push system from v2.11.0
  remains unchanged (for browser/home-screen installs).

v2.11.0:
- BOTH old notification options removed (the v2.10.1 in-app banner
  alerts and the v2.10.2 ntfy/Gotify/Pushover server push). Replaced
  by ONE zero-configuration system: standard Web Push notifications
  (RFC 8030/8291/8292). No third-party apps, no accounts, no URLs or
  tokens to paste — the server auto-generates its VAPID key pair and
  each user enables notifications per device with one tap in
  Settings -> Notifications. Delivery goes through the browser's
  built-in push service; alerts appear on the phone's notification
  screen even when the app is closed.
- All required crypto (P-256 ECDH/ECDSA, HKDF, AES-128-GCM) lives in
  this file, pure Python stdlib — the zero-dependency property of the
  server is preserved. Validated against the FIPS-197 AES vector and
  the complete RFC 8291 example, re-checked at every startup.
- The background checker still runs about every six hours
  (PUSH_CHECK_SECONDS); each subscriber gets an alert for the
  households they can see when an item's status tag worsens. The
  first run only establishes the baseline. Expired subscriptions
  (HTTP 404/410) are pruned automatically.
- New endpoints: GET /api/push/vapid, GET /api/push/status,
  POST /api/push/subscribe, POST /api/push/unsubscribe,
  POST /api/push/test. Removed: GET/POST /api/admin/push and
  POST /api/admin/push/test. New static file sw.js (the service
  worker that displays the notifications), served at /sw.js with
  "Service-Worker-Allowed: /".

v2.10.2:
- Real push notifications: a background checker on the server (about
  every six hours) watches every household's inventory and pushes an
  alert to your phone when an item changes status tag ("less than 6
  months", "less than 3 months", "less than 1 month", expired) — even
  when the app is not open. Pushes go through ntfy, Gotify or Pushover,
  configured in Settings -> Notifications (global admin). New
  endpoints: GET/POST /api/admin/push, POST /api/admin/push/test.
  The in-app banner alerts from v2.10.1 remain as a complement.

v2.10.1:
- The separate Barcodes tab is gone: barcode data now lives in the
  Products tab. /api/data products each carry their "barcodes" list,
  the product list has a filterable Barcode column (add/remove behind
  the Edit button, global admin), and the country barcode list import
  moved from Settings to a card in the Products tab.
- Notifications fixed on the phone app: the Android WebView never
  grants the Notification permission, so alerts there (and anywhere
  permission is missing) now also use an in-app banner + vibration.
- The downloadable APK is always named after the current version
  (app-version.txt -> 2.10.1) even though the app binary is unchanged.

v2.10:
- Pure UI reorganisation; the only server change is the version bump:
  - "Types & Categories" moves from Settings to a tab on the main page
    (global admin only, editing behind an Edit button)
  - the big list filters are gone; per-column filters remain
  - barcode mappings are editable inline in the Barcodes tab's edit mode
  - client-side notifications: Settings -> Notifications toggles alerts
    for items that change status tag (less than 6 months etc.)
  - product removal is locked behind an edit button
  The downloadable APK is always named after the current version
  (app-version.txt -> 2.10.0) even though the app binary is unchanged -
  it is a thin WebView wrapper.

v2.9:
- Barcode reference lists are now opt-in per country: nothing is seeded
  at startup any more. A global admin imports a bundled country list
  (currently: Sweden) in Settings - Barcodes. Imports run once per
  country and are additive; admin deletions stick.
- New endpoints: GET /api/admin/barcode-countries,
  POST /api/admin/barcodes/import
- /api/products accepts an optional barcode (6-14 digits) and maps it
- Size is free text and may contain "/" (e.g. "500/350 g")
- /api/admin/barcodes now also reports the product size

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
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
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
USERS_FILE = os.path.join(CONFIG_DIR, "users.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")   # global product list
PORT = int(os.environ.get("PORT", "4500"))
# v2.11: how often the background web-push checker runs (seconds)
PUSH_CHECK_SECONDS = int(os.environ.get("PUSH_CHECK_SECONDS", "21600"))

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
    # v2.9: "/" allowed in the size field (e.g. "500/350 g")
    return bool(re.fullmatch(r"[\w\s.,'’\-()/åäöÅÄÖéèàü0-9]*", s or "", re.UNICODE))


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
    cfg.setdefault("barcode_imports", {})    # v2.9: imported country lists
    # v2.11: web push subscriptions + auto-generated VAPID key pair.
    # Zero configuration: keys are created on first start, kept in
    # config.json, and the public key is handed to browsers on demand.
    cfg.setdefault("push_subs", [])
    if not cfg.get("vapid_priv"):
        _vpriv = secrets.randbelow(WP_N - 1) + 1
        cfg["vapid_priv"] = b64u_encode(_vpriv.to_bytes(32, "big"))
        cfg["vapid_pub"] = b64u_encode(wp_point_raw(wp_pubkey(_vpriv)))
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


def touch_session(handler):
    """v2.12: extend the caller's session (sliding expiry) — the
    Android app's background poll uses this to stay logged in."""
    cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    if cookie.get("session"):
        s = SESSIONS.get(cookie["session"].value)
        if s and s["expires"] > now():
            s["expires"] = now() + SESSION_TTL


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


def barcode_countries():
    """v2.9: bundled country barcode reference lists (data/barcode-defaults.json)."""
    try:
        with open(BARCODE_DEFAULTS_FILE, encoding="utf-8") as f:
            defaults = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        defaults = {}
    if not isinstance(defaults, dict):
        defaults = {}
    imported = get_config().setdefault("barcode_imports", {})
    out = []
    for code, spec in defaults.items():
        items = spec.get("items", []) if isinstance(spec, dict) else []
        out.append({"country": code,
                    "label": (spec.get("label", code)
                              if isinstance(spec, dict) else code),
                    "count": len(items),
                    "imported": bool(imported.get(code))})
    return out


def import_barcode_country(country):
    """v2.9: import a bundled country barcode list on demand.

    Runs once per country (tracked in config "barcode_imports"); adds any
    missing products to the global product list and maps their barcodes.
    Never overwrites existing products or mappings, and admin deletions
    stick - the import is not re-run for that country.
    """
    country = str(country or "").strip().lower()
    try:
        with open(BARCODE_DEFAULTS_FILE, encoding="utf-8") as f:
            defaults = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        defaults = {}
    spec = defaults.get(country) if isinstance(defaults, dict) else None
    if not isinstance(spec, dict) or not isinstance(spec.get("items"), list):
        raise ValueError("Unknown country barcode list.")
    cfg = get_config()
    imported = cfg.setdefault("barcode_imports", {})
    if imported.get(country):
        return {"country": country, "added": 0, "mapped": 0, "already": True}
    type_ids = {t["id"] for t in get_food_types()}
    products = read_csv(PRODUCTS_CSV)
    seen = {(p.get("name", "").lower(), p.get("manufacturer", "").lower())
            for p in products}
    barcodes = cfg.setdefault("barcodes", {})
    added = mapped = 0
    for d in spec["items"]:
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
    imported[country] = True
    save_json(CONFIG_FILE, cfg)
    return {"country": country, "added": added, "mapped": mapped,
            "already": False}


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


def add_product(name, manufacturer, ftype, category, size, barcode=None):
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
    if barcode:
        code = str(barcode).strip()
        if not re.fullmatch(r"[0-9]{6,14}", code):
            raise ValueError("Barcode must be 6-14 digits.")
        cfg = get_config()
        cfg.setdefault("barcodes", {})[code] = {
            "name": name, "manufacturer": manufacturer}
        save_json(CONFIG_FILE, cfg)


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
    """Global product list, each product with its mapped barcodes (v2.10.1)."""
    products = read_csv(PRODUCTS_CSV)
    by_prod = {}
    for code, v in get_config().get("barcodes", {}).items():
        key = (str(v.get("name", "")).lower(),
               str(v.get("manufacturer", "")).lower())
        by_prod.setdefault(key, []).append(code)
    for p in products:
        p["barcodes"] = by_prod.get(
            (p.get("name", "").lower(), p.get("manufacturer", "").lower()), [])
    return products


# ======================= web push notifications (v2.11) =======================
#
# Zero-configuration push notifications via the standard Web Push
# protocol (RFC 8030 + RFC 8291 encryption + RFC 8292 VAPID auth).
# Delivery goes through the browser's built-in push service: the user
# never installs a third-party app, creates an account, or pastes a
# token. All crypto below is pure Python stdlib (P-256 ECDH/ECDSA,
# HKDF, AES-128-GCM) so the server keeps its zero-dependency design.
# The primitives are validated at startup against the FIPS-197 AES
# test vector and the complete RFC 8291 section 5 example.

PUSH_LEVEL_TEXT = {"ok": "fine", "6months": "less than 6 months",
                   "3months": "less than 3 months",
                   "1month": "less than 1 month", "expired": "expired"}
PUSH_RANK = {"ok": 0, "6months": 1, "3months": 2, "1month": 3, "expired": 4}


#!/usr/bin/env python3
"""Web Push crypto primitives, pure Python stdlib.
Validated against FIPS-197 AES-128, the full RFC 8291 §5/Appendix WP_A vector,
and OpenSSL (via Node crypto) GCM oracle samples."""
import base64, hashlib, hmac, secrets


# ---------------- WP_P-256 (secp256r1) ----------------
WP_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
WP_A = WP_P - 3
WP_G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
     0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)
WP_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _wp_add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2:
        if (y1 + y2) % WP_P == 0:
            return None
        lam = (3 * x1 * x1 + WP_A) * pow(2 * y1, -1, WP_P) % WP_P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, WP_P) % WP_P
    x3 = (lam * lam - x1 - x2) % WP_P
    return x3, (lam * (x1 - x3) - y1) % WP_P


def _wp_mul(k, p):
    r = None
    while k:
        if k & 1:
            r = _wp_add(r, p)
        p = _wp_add(p, p)
        k >>= 1
    return r


def wp_pubkey(priv):
    return _wp_mul(priv, WP_G)


def wp_point_raw(pt):
    return b"\x04" + pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big")


def wp_point_from_raw(raw):
    if len(raw) != 65 or raw[0] != 4:
        raise ValueError("Bad WP_P-256 public key.")
    return int.from_bytes(raw[1:33], "big"), int.from_bytes(raw[33:65], "big")


def b64u_encode(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64u_decode(s):
    s = str(s).strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------- AES-128 ----------------
def _wp_gmul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return r


def _wp_make_sbox():
    log, alog, x = [0] * 256, [0] * 512, 1
    for i in range(255):
        alog[i] = x
        log[x] = i
        x = _wp_gmul(x, 3)
    for i in range(255, 512):
        alog[i] = alog[i - 255]
    sbox = [0x63] * 256
    for a in range(1, 256):
        inv = alog[255 - log[a]]
        s, r = inv, inv
        for _ in range(4):
            r = ((r << 1) | (r >> 7)) & 0xFF
            s ^= r
        sbox[a] = s ^ 0x63
    return sbox


WP_SBOX = _wp_make_sbox()
WP_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _wp_xt(a):
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def wp_aes_expand(key):
    w = [list(key[0:4]), list(key[4:8]), list(key[8:12]), list(key[12:16])]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [WP_SBOX[b] for b in t]
            t[0] ^= WP_RCON[i // 4 - 1]
        w.append([x ^ y for x, y in zip(w[i - 4], t)])
    return [w[4 * r] + w[4 * r + 1] + w[4 * r + 2] + w[4 * r + 3] for r in range(11)]


def wp_aes_block(rk, b):
    s = [b[i] ^ rk[0][i] for i in range(16)]
    for rnd in range(1, 11):
        s = [WP_SBOX[c] for c in s]
        s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3],
             s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
        if rnd < 10:
            t = []
            for c in range(0, 16, 4):
                a = s[c:c + 4]
                t += [(_wp_xt(a[0]) ^ _wp_xt(a[1]) ^ a[1]) ^ a[2] ^ a[3],
                      a[0] ^ (_wp_xt(a[1]) ^ _wp_xt(a[2]) ^ a[2]) ^ a[3],
                      a[0] ^ a[1] ^ (_wp_xt(a[2]) ^ _wp_xt(a[3]) ^ a[3]),
                      (_wp_xt(a[3]) ^ _wp_xt(a[0]) ^ a[0]) ^ a[1] ^ a[2]]
            s = t
        s = [s[i] ^ rk[rnd][i] for i in range(16)]
    return bytes(s)


# ---------------- AES-128-GCM ----------------
def _wp_gf128(x, y):
    """GHASH block multiplication (SP 800-38D Algorithm 1; MSB = x^0,
    LSB = x^127, field poly 1 + a + a^2 + a^7 + a^128)."""
    R = 0xE1 << 120
    res = 0
    for i in range(127, -1, -1):
        if (y >> i) & 1:
            res ^= x
        x = (x >> 1) ^ ((x & 1) * R)
    return res


def wp_gcm_encrypt(key, nonce12, data):
    """AES-128-GCM encrypt with no AAD; returns (ct, tag)."""
    rk = wp_aes_expand(key)
    h = int.from_bytes(wp_aes_block(rk, b"\x00" * 16), "big")
    j0 = nonce12 + b"\x00\x00\x00\x01"
    ctr = int.from_bytes(j0, "big") + 1
    ct = bytearray()
    for i in range(0, len(data), 16):
        ks = wp_aes_block(rk, ctr.to_bytes(16, "big"))
        ctr += 1
        ct += bytes(x ^ y for x, y in zip(data[i:i + 16], ks))
    # GHASH over ciphertext (no AAD), then the length block (0-bit AAD len)
    y = 0
    for i in range(0, len(ct), 16):
        y = _wp_gf128(y ^ int.from_bytes(bytes(ct[i:i + 16]).ljust(16, b"\x00"), "big"), h)
    y = _wp_gf128(y ^ (len(ct) << 3), h)
    tag = bytes(x ^ y for x, y in zip(wp_aes_block(rk, j0), y.to_bytes(16, "big")))
    return bytes(ct), tag


# ---------------- ECDSA (ES256, RFC 8292 VAPID) ----------------
def wp_es256_sign(priv, msg):
    h = int.from_bytes(hashlib.sha256(msg).digest(), "big")
    while True:
        k = secrets.randbelow(WP_N - 1) + 1
        R = _wp_mul(k, WP_G)
        r = R[0] % WP_N
        if r == 0:
            continue
        s = pow(k, -1, WP_N) * (h + r * priv) % WP_N
        if s != 0:
            return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def wp_es256_verify(pub_raw, msg, sig):
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:64], "big")
    h = int.from_bytes(hashlib.sha256(msg).digest(), "big")
    Q = wp_point_from_raw(pub_raw)
    w = pow(s, -1, WP_N)
    u1 = h * w % WP_N
    u2 = r * w % WP_N
    pt = _wp_add(_wp_mul(u1, WP_G), _wp_mul(u2, Q))
    return pt is not None and pt[0] % WP_N == r


# ---------------- RFC 8291 message encryption ----------------
def _wp_hkdf_info(prk_key, info):
    return hmac.new(prk_key, info + b"\x01", hashlib.sha256).digest()


def wp_encrypt_payload(ua_pub_raw, auth_secret, plaintext, as_priv=None, salt=None):
    """RFC 8291 aes128gcm encryption. Returns the full body (header+ct+tag).
    as_priv/salt can be fixed for tests."""
    ua = wp_point_from_raw(ua_pub_raw)
    if as_priv is None:
        as_priv = secrets.randbelow(WP_N - 1) + 1
    as_pt = wp_pubkey(as_priv)
    as_raw = wp_point_raw(as_pt)
    ecdh = _wp_mul(as_priv, ua)
    ecdh_secret = ecdh[0].to_bytes(32, "big")
    # PRK_key = HKDF-Extract(auth_secret, ecdh_secret)
    prk_key = hmac.new(auth_secret, ecdh_secret, hashlib.sha256).digest()
    # IKM = HKDF-Expand(PRK_key, key_info || 0x01, 32)
    key_info = b"WebPush: info" + b"\x00" + ua_pub_raw + as_raw
    ikm = _wp_hkdf_info(prk_key, key_info)
    if salt is None:
        salt = secrets.token_bytes(16)
    # PRK = HKDF-Extract(salt, IKM)
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    cek = hmac.new(prk, b"Content-Encoding: aes128gcm" + b"\x00" + b"\x01",
                  hashlib.sha256).digest()[:16]
    nonce = hmac.new(prk, b"Content-Encoding: nonce" + b"\x00" + b"\x01",
                     hashlib.sha256).digest()[:12]
    # RFC 8188 header: salt(16) | rs(4, 4096) | keyid_len(1) | keyid
    header = salt + (4096).to_bytes(4, "big") + bytes([65]) + as_raw
    pt = plaintext + b"\x02"      # single record, pad delimiter
    ct, tag = wp_gcm_encrypt(cek, nonce, pt)
    return header + ct + tag




def webpush_selftest():
    """Validate the crypto at startup against known-good vectors."""
    rk = wp_aes_expand(bytes(range(16)))
    assert wp_aes_block(rk, bytes.fromhex("00112233445566778899aabbccddeeff")) \
        .hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"     # FIPS-197 C.1
    body = wp_encrypt_payload(
        b64u_decode("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-"
                    "AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"),
        b64u_decode("BTBZMqHH6r4Tts7J_aSIgg"),
        b"When I grow up, I want to be a watermelon",
        as_priv=int.from_bytes(b64u_decode(
            "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"),
        salt=b64u_decode("DGv6ra1nlYgDCS1FRnbzlw"))
    want = ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
            "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
            "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")
    assert b64u_encode(body) == want, "RFC 8291 self-test failed"


def send_web_push(sub, title, body):
    """Send one Web Push message (RFC 8291/8292) to a subscription.

    Returns (ok, error, expired); expired=True means the subscription
    is gone (HTTP 404/410) and should be pruned.
    """
    cfg = get_config()
    try:
        payload = json.dumps({"title": title, "body": body[:3000],
                              "tag": "food-alert", "url": "/"}).encode("utf-8")
        encrypted = wp_encrypt_payload(b64u_decode(sub["p256dh"]),
                                       b64u_decode(sub["auth"]), payload)
        endpoint = str(sub["endpoint"])
        u = urllib.parse.urlparse(endpoint)
        aud = f"{u.scheme}://{u.netloc}"
        priv = int.from_bytes(b64u_decode(cfg["vapid_priv"]), "big")
        head = json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":"))
        claims = json.dumps({"aud": aud, "exp": int(time.time()) + 43200,
                             "sub": "mailto:admin@emergency-food-tracker.local"},
                            separators=(",", ":"))
        signing_input = (b64u_encode(head.encode("utf-8")) + "." +
                        b64u_encode(claims.encode("utf-8"))).encode("utf-8")
        sig = wp_es256_sign(priv, signing_input)
        jwt = signing_input.decode() + "." + b64u_encode(sig)
        req = urllib.request.Request(endpoint, data=encrypted, headers={
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "aes128gcm",
            "TTL": "86400",
            "Urgency": "high",
            "Authorization": f"vapid t={jwt}, k={cfg['vapid_pub']}",
            "User-Agent": "emergency-food-tracker"})
        try:
            urllib.request.urlopen(req, timeout=15)
            return True, "", False
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return False, f"subscription expired (HTTP {e.code})", True
            return False, f"push service returned HTTP {e.code}", False
    except Exception as e:
        return False, str(e), False


def run_push_check():
    """Compare every item's status tag with the previous check and send
    each subscriber a Web Push for the households they can see. The
    first run only establishes the baseline (no push)."""
    cfg = get_config()
    subs = cfg.get("push_subs") or []
    prev = cfg.get("push_levels", {})
    cur = {}
    changed = {}                      # household -> [alert lines]
    for hh in list_households():
        for r in inventory_view(hh):
            key = f"{hh}:{r['id']}"
            level = r.get("level", "ok")
            cur[key] = level
            old = prev.get(key)
            if old and old != level and PUSH_RANK.get(level, 0) > PUSH_RANK.get(old, 0):
                name = r.get("product", "")
                man = r.get("manufacturer", "")
                label = f"{name} ({man})" if man else name
                changed.setdefault(hh, []).append(
                    f"{label}: {PUSH_LEVEL_TEXT.get(old, old)} -> "
                    f"{PUSH_LEVEL_TEXT.get(level, level)}")
    cfg["push_levels"] = cur
    save_json(CONFIG_FILE, cfg)
    if not subs or not changed:
        return
    dead = []
    for sub in subs:
        user = find_user(str(sub.get("user", "")))
        if not user:
            dead.append(sub)          # user deleted -> prune
            continue
        hhs = list_households() if is_global_admin(user) else user_households(user)
        lines = [line for hh in hhs for line in changed.get(hh, [])]
        if not lines:
            continue
        body = "\n".join(lines[:20])
        if len(lines) > 20:
            body += f"\n... and {len(lines) - 20} more"
        ok, err, expired = send_web_push(sub, "Food storage alert", body)
        if expired:
            dead.append(sub)
        elif not ok:
            print("web push failed:", err)
    if dead:
        for d in dead:
            try:
                subs.remove(d)
            except ValueError:
                pass
        cfg["push_subs"] = subs
        save_json(CONFIG_FILE, cfg)


def push_loop():
    while True:
        time.sleep(PUSH_CHECK_SECONDS)
        try:
            run_push_check()
        except Exception as e:
            print("push check failed:", e)


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
            elif path == "/sw.js":
                # v2.11: service worker for Web Push. Served at the root
                # with Service-Worker-Allowed so its scope covers the app.
                try:
                    with open(os.path.join(STATIC_DIR, "sw.js"), "rb") as f:
                        sw = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript")
                    self.send_header("Content-Length", str(len(sw)))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Service-Worker-Allowed", "/")
                    self.end_headers()
                    self.wfile.write(sw)
                except FileNotFoundError:
                    self.reply(404, {"error": "sw.js not found"})
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
                    "version": "2.12.7",
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
            elif path == "/api/admin/barcode-countries":
                # v2.9: bundled country barcode lists + import status
                require_global_admin(self)
                self.reply(200, {"countries": barcode_countries()})
            elif path == "/api/push/vapid":
                # v2.11: the server's auto-generated VAPID public key
                require_user(self)
                self.reply(200, {"publicKey": get_config().get("vapid_pub", "")})
            elif path == "/api/push/status":
                # v2.11: the current user's push subscriptions
                user = require_user(self)
                subs = [s for s in get_config().get("push_subs", [])
                        if s.get("user") == user["username"]]
                self.reply(200, {"endpoints": [s.get("endpoint", "") for s in subs]})
            elif path == "/api/push/inbox":
                # v2.12: native Android app poll — alerts for the
                # households this user can see, since this device's
                # last poll. The device auto-registers on first poll.
                user = require_user(self)
                dev = (qs.get("device") or [""])[0].strip()
                if not dev or len(dev) > 100:
                    raise ValueError("Missing device id.")
                cfg = get_config()
                devs = cfg.setdefault("push_devices", {})
                d = devs.get(dev)
                if d and d.get("user") != user["username"]:
                    raise ValueError("Device is registered to another user.")
                if d is None:
                    d = {"user": user["username"], "levels": {}}
                    devs[dev] = d
                d["last_seen"] = date.today().isoformat()
                hhs = list_households() if is_global_admin(user) \
                    else user_households(user)
                prev = d.get("levels") or {}
                cur, alerts = {}, []
                for hh in hhs:
                    for r in inventory_view(hh):
                        key = f"{hh}:{r['id']}"
                        level = r.get("level", "ok")
                        cur[key] = level
                        old = prev.get(key)
                        if old and old != level and \
                                PUSH_RANK.get(level, 0) > PUSH_RANK.get(old, 0):
                            name = r.get("product", "")
                            man = r.get("manufacturer", "")
                            label = f"{name} ({man})" if man else name
                            alerts.append(
                                f"{label}: {PUSH_LEVEL_TEXT.get(old, old)} -> "
                                f"{PUSH_LEVEL_TEXT.get(level, level)}")
                d["levels"] = cur
                # prune devices that have not polled in 90 days
                cutoff = (date.today() - timedelta(days=90)).isoformat()
                for k in [k for k, v in devs.items()
                          if str(v.get("last_seen", "")) < cutoff]:
                    devs.pop(k, None)
                save_json(CONFIG_FILE, cfg)
                touch_session(self)   # polling keeps the app session alive
                self.reply(200, {"alerts": alerts[:20],
                                 "more": max(0, len(alerts) - 20)})
            elif path == "/api/admin/barcodes":
                # v2.7: list barcode -> product mappings (v2.9: with size)
                require_global_admin(self)
                bc = get_config().get("barcodes", {})
                prods = {(p.get("name", "").lower(),
                          p.get("manufacturer", "").lower()): p
                         for p in read_csv(PRODUCTS_CSV)}
                out = []
                for code, v in bc.items():
                    p = prods.get((v.get("name", "").lower(),
                                   v.get("manufacturer", "").lower()), {})
                    out.append({"barcode": code, "name": v.get("name", ""),
                                "manufacturer": v.get("manufacturer", ""),
                                "size": p.get("size", "")})
                self.reply(200, {"barcodes": out})
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
                            body.get("size", ""), body.get("barcode", ""))
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
            elif path == "/api/admin/barcodes/import":
                # v2.9: import a bundled country barcode list on demand
                require_global_admin(self)
                res = import_barcode_country(body.get("country", ""))
                self.reply(200, {"ok": True, **res})
            elif path == "/api/push/subscribe":
                # v2.11: register this browser for push notifications
                user = require_user(self)
                s = body.get("subscription") or body
                endpoint = str(s.get("endpoint") or "").strip()
                keys = s.get("keys") or {}
                p256dh = str(keys.get("p256dh") or s.get("p256dh") or "").strip()
                auth = str(keys.get("auth") or s.get("auth") or "").strip()
                if not (endpoint.startswith("http://") or
                        endpoint.startswith("https://")) or not p256dh or not auth:
                    raise ValueError("Incomplete push subscription.")
                b64u_decode(p256dh)     # must be valid base64url
                b64u_decode(auth)
                cfg = get_config()
                subs = cfg.setdefault("push_subs", [])
                sub = None
                for e in subs:
                    if e.get("endpoint") == endpoint:
                        sub = e
                        break
                if sub is None:
                    sub = {"endpoint": endpoint}
                    subs.append(sub)
                sub.update({"p256dh": p256dh, "auth": auth,
                            "user": user["username"],
                            "added": date.today().isoformat()})
                save_json(CONFIG_FILE, cfg)
                send_web_push(sub, "Food storage tracker",
                              "Notifications enabled - you will be alerted "
                              "here when items start expiring.")
                self.reply(200, {"ok": True})
            elif path == "/api/push/unsubscribe":
                # v2.11: remove one of the current user's subscriptions
                user = require_user(self)
                endpoint = str(body.get("endpoint") or "").strip()
                cfg = get_config()
                subs = cfg.setdefault("push_subs", [])
                before = len(subs)
                cfg["push_subs"] = [s for s in subs
                                    if not (s.get("endpoint") == endpoint and
                                            s.get("user") == user["username"])]
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True,
                                 "removed": before - len(cfg["push_subs"])})
            elif path == "/api/push/test":
                # v2.11: send a test push to the current user's devices
                user = require_user(self)
                subs = [s for s in get_config().get("push_subs", [])
                        if s.get("user") == user["username"]]
                if not subs:
                    raise ValueError("No device has notifications enabled yet.")
                sent = 0
                errs = []
                for sub in subs:
                    ok, err, expired = send_web_push(
                        sub, "Food storage tracker",
                        "Test notification - server notifications work.")
                    if ok:
                        sent += 1
                    else:
                        errs.append(err)
                if not sent:
                    raise ValueError("Push failed: " + "; ".join(errs[:2]))
                self.reply(200, {"ok": True, "sent": sent})
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
    get_users()   # normalizes roles + generates per-user API keys
    get_config()
    webpush_selftest()          # crypto sanity (FIPS-197 + RFC 8291)
    # v2.11: background web-push checker (daemon)
    threading.Thread(target=push_loop, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Food storage tracker v2.12.7: http://0.0.0.0:{PORT} "
          f"(data: {DATA_DIR}, config: {CONFIG_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()

