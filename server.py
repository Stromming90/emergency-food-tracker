#!/usr/bin/env python3
"""
Emergency Food Storage Tracker — Web UI server (multi-user, multi-household)
===========================================================================
Zero-dependency web server (Python stdlib only).

Features:
- User accounts with sessions (first run: create admin account)
- Households: each user can belong to several, inventory is per-household
- OIDC login (e.g. Keycloak) — configure via admin UI or env vars
- Expiry alerts: 6 months / 3 months / 1 month / expired
- Homepage (gethomepage) widget API: /api/widget
- Dark mode: handled client-side in static/index.html

Environment variables:
  DATA_DIR   where household CSV data lives   (default ./data)
  CONFIG_DIR where users/config live          (default ./config)
  PORT       listen port                      (default 8000)
  OIDC_*     optional OIDC overrides (ISSUER, CLIENT_ID, CLIENT_SECRET,
             SCOPES, ADMIN_EMAILS)

In Docker mount both /data and /config as volumes.
"""

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
USERS_FILE = os.path.join(CONFIG_DIR, "users.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PORT = int(os.environ.get("PORT", "8000"))

ALERT_WINDOWS = {"6months": 180, "3months": 90, "1month": 30}
PRODUCTS_HEADER = ["name", "manufacturer", "category", "added_date"]
INVENTORY_HEADER = ["id", "product", "manufacturer", "best_before", "quantity", "added_date"]

SESSIONS = {}          # token -> {username, expires}
SESSION_TTL = 7 * 24 * 3600


# ======================= small utilities =======================

def now():
    return int(time.time())


def today():
    return date.today()


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def slugify(s):
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9åäö\-_]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "default"


def valid_name(s):
    return bool(re.fullmatch(r"[\w\s.,'’\-()åäöÅÄÖéèàü0-9]*", s or "", re.UNICODE))


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


# ======================= config =======================

def get_config():
    cfg = load_json(CONFIG_FILE, {})
    changed = False
    if "api_key" not in cfg:
        cfg["api_key"] = secrets.token_urlsafe(24)
        changed = True
    oidc = cfg.setdefault("oidc", {})
    # env overrides
    for env_key, key in (("OIDC_ISSUER", "issuer"), ("OIDC_CLIENT_ID", "client_id"),
                         ("OIDC_CLIENT_SECRET", "client_secret")):
        if os.environ.get(env_key):
            oidc[key] = os.environ[env_key]
    if os.environ.get("OIDC_ADMIN_EMAILS"):
        oidc["admin_emails"] = [e.strip() for e in os.environ["OIDC_ADMIN_EMAILS"].split(",") if e.strip()]
    if "admin_emails" not in oidc:
        oidc["admin_emails"] = []
    if changed:
        save_json(CONFIG_FILE, cfg)
    return cfg


def oidc_enabled():
    oidc = get_config()["oidc"]
    return bool(oidc.get("issuer") and oidc.get("client_id"))


def oidc_discovery(oidc):
    """Discover endpoints from the issuer's well-known document (cached)."""
    if "endpoints" in oidc:
        return oidc["endpoints"]
    base = oidc["issuer"].rstrip("/")
    url = base + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
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


# ======================= users =======================

def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 100_000)
    return salt, digest.hex()


def get_users():
    return load_json(USERS_FILE, {"users": []})


def save_users(u):
    save_json(USERS_FILE, u)


def user_count():
    return len(get_users()["users"])


def find_user(username):
    for u in get_users()["users"]:
        if u["username"].lower() == username.lower():
            return u
    return None


def check_password(user, pw):
    try:
        salt, expect = user["password"].split("$", 1)
    except (KeyError, ValueError):
        return False
    _, got = hash_password(pw, salt)
    return hmac.compare_digest(expect, got)


def create_user(username, password, is_admin=False, households=None, oidc_sub=None, email=None):
    if not valid_name(username) or not username.strip():
        raise ValueError("Invalid username.")
    if len(username) > 40:
        raise ValueError("Username too long.")
    if find_user(username):
        raise ValueError("User already exists.")
    if password and len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt, ph = hash_password(password) if password else ("", "")
    users = get_users()
    users["users"].append({
        "username": username.strip(),
        "password": f"{salt}${ph}" if ph else "",
        "is_admin": bool(is_admin),
        "households": households or ["default"],
        "oidc_sub": oidc_sub,
        "email": email,
    })
    save_users(users)


# ======================= sessions =======================

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


def require_user(handler):
    user = current_user(handler)
    if not user:
        raise AuthError("Not logged in.")
    return user


class AuthError(Exception):
    pass


def allowed_household(user, household):
    return household in user.get("households", []) or user.get("is_admin")


def user_households(user):
    return sorted(set(user.get("households", [])))


# ======================= households / storage =======================

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
    for path, header in ((os.path.join(hdir, "products.csv"), PRODUCTS_HEADER),
                         (os.path.join(hdir, "inventory.csv"), INVENTORY_HEADER)):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(header)
            continue
        with open(path, newline="", encoding="utf-8") as f:
            current = next(csv.reader(f), None) or []
        if current != header:  # migrate old schema
            rows = [{h: r.get(h, "") for h in header}
                    for r in csv.DictReader(open(path, newline="", encoding="utf-8"))]
            tmp = path + ".tmp"
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=header)
                w.writeheader()
                w.writerows(rows)
            os.replace(tmp, path)


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


# ---------- per-household model (same logic as before, scoped) ----------

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


def add_product(household, name, manufacturer, category):
    ensure_household(household)
    path = os.path.join(household_dir(household), "products.csv")
    name, manufacturer, category = name.strip(), (manufacturer or "").strip(), (category or "").strip()
    if not name:
        raise ValueError("Product name is required.")
    if not valid_name(name) or not valid_name(manufacturer):
        raise ValueError("Product name/manufacturer contains invalid characters.")
    products = read_csv(path)
    if any(p["name"].lower() == name.lower()
           and p.get("manufacturer", "").lower() == manufacturer.lower()
           for p in products):
        raise ValueError(f"'{name}' by '{manufacturer or 'unknown maker'}' is already on the list.")
    products.append({"name": name, "manufacturer": manufacturer, "category": category,
                     "added_date": today().isoformat()})
    products.sort(key=lambda p: (p["name"].lower(), p.get("manufacturer", "").lower()))
    write_csv(path, PRODUCTS_HEADER, products)


def buy(household, product, manufacturer, best_before, quantity):
    ensure_household(household)
    inv_path = os.path.join(household_dir(household), "inventory.csv")
    product = product.strip()
    manufacturer = (manufacturer or "").strip()
    prod_path = os.path.join(household_dir(household), "products.csv")
    if not any(p["name"].lower() == product.lower()
               and p.get("manufacturer", "").lower() == manufacturer.lower()
               for p in read_csv(prod_path)):
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


def remove_product(household, name, manufacturer=None):
    ensure_household(household)
    prod_path = os.path.join(household_dir(household), "products.csv")
    products = read_csv(prod_path)
    name_l, man_l = name.lower(), (manufacturer or "").lower()
    matching = [p for p in products
                if p["name"].lower() == name_l
                and (manufacturer is None or p.get("manufacturer", "").lower() == man_l)]
    if not matching:
        raise ValueError("Product not found.")
    keep = {(p["name"].lower(), p.get("manufacturer", "").lower()) for p in matching}
    inv = read_csv(os.path.join(household_dir(household), "inventory.csv"))
    if any((r["product"].lower(), r.get("manufacturer", "").lower()) in keep for r in inv):
        raise ValueError("Product still has items in the inventory; remove them first.")
    write_csv(prod_path, PRODUCTS_HEADER,
              [p for p in products
               if (p["name"].lower(), p.get("manufacturer", "").lower()) not in keep])


def inventory_view(household):
    ensure_household(household)
    rows = []
    for r in read_csv(os.path.join(household_dir(household), "inventory.csv")):
        best = parse_date(r["best_before"])
        days = (best - today()).days
        rows.append({"id": int(r["id"]), "product": r["product"],
                     "manufacturer": r.get("manufacturer", ""),
                     "best_before": r["best_before"], "quantity": int(r["quantity"]),
                     "days_left": days, "level": alert_level(best)})
    rows.sort(key=lambda r: r["days_left"])
    return rows


def products_view(household):
    ensure_household(household)
    return read_csv(os.path.join(household_dir(household), "products.csv"))


# ======================= HTTP =======================

def send_redirect(handler, location, set_cookie=None):
    handler.send_response(302)
    handler.send_header("Location", location)
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    # ---------- helpers ----------
    def reply(self, code, body, content_type="application/json", set_cookie=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data))
                         if isinstance(data, bytes) else str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        if data:
            self.wfile.write(data if isinstance(data, bytes) else data.encode())

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
        household = (body or {}).get("household") or (qs.get("household", [None])[0]) or "default"
        if not allowed_household(user, household):
            raise AuthError(f"No access to household '{household}'.")
        return household

    # ---------- routes ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                    self.reply(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/bootstrap":
                user = current_user(self)
                cfg = get_config()
                self.reply(200, {
                    "configured": user_count() > 0,
                    "oidc_enabled": oidc_enabled(),
                    "oidc_name": cfg["oidc"].get("issuer", "").rstrip("/").split("//")[-1],
                    "user": (dict(username=user["username"],
                                  is_admin=user.get("is_admin", False),
                                  households=user_households(user)) if user else None),
                })
            elif path == "/api/data":
                user = require_user(self)
                h = self.household_of(user)
                self.reply(200, {"products": products_view(h),
                                 "inventory": inventory_view(h),
                                 "today": today().isoformat(),
                                 "household": h})
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
            # ---------- admin listings ----------
            elif path == "/api/admin/users":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                users = get_users()["users"]
                self.reply(200, {"users": [
                    {"username": u["username"], "is_admin": u.get("is_admin", False),
                     "households": u.get("households", []), "email": u.get("email", ""),
                     "oidc": bool(u.get("oidc_sub"))}
                    for u in users]})
            elif path == "/api/admin/households":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                self.reply(200, {"households": list_households()})
            elif path == "/api/admin/config":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                oidc = get_config()["oidc"]
                self.reply(200, {"api_key": get_config()["api_key"],
                                 "oidc": {k: oidc.get(k, "")
                                          for k in ("issuer", "client_id", "client_secret",
                                                    "redirect_uri", "scopes", "admin_emails")},
                                 "oidc_auto_create": oidc.get("auto_create", True),
                                 "oidc_enabled": oidc_enabled()})
            # ---- homepage widget ----
            elif path == "/api/widget":
                key = qs.get("key", [""])[0]
                household = qs.get("household", ["default"])[0]
                cfg = get_config()
                if not hmac.compare_digest(key, cfg.get("api_key", "")):
                    self.reply(401, {"error": "invalid key"})
                    return
                inv = inventory_view(household)
                counts = {"expired": 0, "1month": 0, "3months": 0, "6months": 0, "ok": 0}
                for r in inv:
                    counts[r["level"]] += 1
                soon = counts["1month"] + counts["3months"] + counts["6months"]
                alerts = []
                for r in inv:
                    if r["level"] == "expired":
                        alerts.append(f"EXPIRED: {r['product']} (best before {r['best_before']})")
                    elif r["level"] != "ok":
                        alerts.append(f"{r['product']}: {r['days_left']} days left ({r['best_before']})")
                self.reply(200, {
                    "household": household,
                    "total_items": len(inv),
                    "expiring_within_6_months": counts["6months"] + counts["3months"] + counts["1month"],
                    "expiring_within_3_months": counts["3months"] + counts["1month"],
                    "expiring_within_1_month": counts["1month"],
                    "expired": counts["expired"],
                    "attention": soon + counts["expired"],
                    "next_expiries": [
                        {"product": r["product"], "manufacturer": r["manufacturer"],
                         "best_before": r["best_before"], "days_left": r["days_left"],
                         "level": r["level"]}
                        for r in inv if r["level"] != "ok"
                    ][:10],
                    "alerts": alerts[:10],
                })
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except ValueError as e:
            self.reply(400, {"error": str(e)})
        except FileNotFoundError as e:
            self.reply(500, {"error": f"missing file: {e}"})

    def oidc_callback(self, qs):
        oidc = get_config()["oidc"]
        state = qs.get("state", [""])[0]
        if not state or "oidc-state-" + state not in SESSIONS:
            raise ValueError("Invalid OIDC state.")
        SESSIONS.pop("oidc-state-" + state)
        code = qs.get("code", [""])[0]
        if not code:
            raise ValueError("No code from OIDC provider.")
        eps = oidc_discovery(oidc)
        base = oidc.get("redirect_uri") or f"http://{self.headers.get('Host', 'localhost')}/api/oidc/callback"
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": base,
            "client_id": oidc["client_id"],
            "client_secret": oidc.get("client_secret", ""),
        }).encode()
        req = urllib.request.Request(eps["token"], data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as r:
            tok = json.loads(r.read().decode())
        req2 = urllib.request.Request(eps["userinfo"],
                                      headers={"Authorization": "Bearer " + tok["access_token"]})
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
            create_user(username, "", is_admin=is_admin,
                        households=["default"], oidc_sub=info.get("sub"), email=email)
            user = find_user(username)
        token = create_session(user["username"])
        send_redirect(self, "/", self.session_cookie(token))

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
                hh = slugify(body.get("household") or "default")
                ensure_household(hh)
                create_user(body["username"], body["password"], is_admin=True,
                            households=[hh])
                token = create_session(body["username"].strip())
                self.reply(200, {"ok": True}, set_cookie=self.session_cookie(token))
            elif path == "/api/login":
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
            elif path == "/api/products":
                user = require_user(self)
                add_product(self.household_of(user, body), body.get("name", ""),
                            body.get("manufacturer", ""), body.get("category", ""))
                self.reply(201, {"ok": True})
            elif path == "/api/buy":
                user = require_user(self)
                buy(self.household_of(user, body), body.get("product", ""),
                    body.get("manufacturer", ""), body.get("best_before", ""),
                    body.get("quantity", 1))
                self.reply(201, {"ok": True})
            # ---------- admin ----------
            elif path == "/api/admin/users":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                if not body.get("username") or not body.get("password"):
                    raise ValueError("Username and password required.")
                create_user(body["username"], body["password"],
                            is_admin=bool(body.get("is_admin")),
                            households=[slugify(h) for h in body.get("households", ["default"])])
                self.reply(201, {"ok": True})
            elif path == "/api/admin/households":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                hh = slugify(body.get("name", ""))
                ensure_household(hh)
                if hh not in list_households():
                    pass  # created by ensure
                self.reply(201, {"ok": True, "household": hh})
            elif path == "/api/admin/oidc":
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                cfg = get_config()
                oidc = cfg["oidc"]
                for k in ("issuer", "client_id", "client_secret", "redirect_uri", "scopes"):
                    if k in body:
                        oidc[k] = str(body[k]).strip()
                if "auto_create" in body:
                    oidc["auto_create"] = bool(body["auto_create"])
                if isinstance(body.get("admin_emails"), list):
                    oidc["admin_emails"] = [str(e).strip() for e in body["admin_emails"]]
                oidc.pop("endpoints", None)  # force re-discovery
                save_json(CONFIG_FILE, cfg)
                self.reply(200, {"ok": True, "oidc_enabled": oidc_enabled()})
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            user = require_user(self)
            m = re.fullmatch(r"/api/inventory/(\d+)", path)
            if m:
                h = self.household_of(user) if not user.get("is_admin") else \
                    (qs.get("household", [None])[0] or "default")
                if not allowed_household(user, h):
                    raise AuthError(f"No access to household '{h}'.")
                remove_item(h, m.group(1))
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/products/(.+)", path)
            if m:
                h = qs.get("household", [None])[0] or "default"
                if not allowed_household(user, h):
                    raise AuthError(f"No access to household '{h}'.")
                remove_product(h, urllib.parse.unquote(m.group(1)),
                               qs.get("manufacturer", [None])[0])
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/admin/users/(.+)", path)
            if m:
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                users = get_users()
                uname = urllib.parse.unquote(m.group(1))
                if uname.lower() == user["username"].lower():
                    raise ValueError("You cannot delete your own account.")
                remaining = [u for u in users["users"]
                             if u["username"].lower() != uname.lower()]
                if len(remaining) == len(users["users"]):
                    raise ValueError("User not found.")
                users["users"] = remaining
                save_users(users)
                self.reply(200, {"ok": True})
                return
            m = re.fullmatch(r"/api/admin/users/([^/]+)/households", path)
            if m:
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                uname = m.group(1)
                users = get_users()
                target = next((u for u in users["users"]
                               if u["username"].lower() == uname.lower()), None)
                if not target:
                    raise ValueError("User not found.")
                body = self.read_body()
                target["households"] = [slugify(h) for h in body.get("households", [])]
                save_users(users)
                self.reply(200, {"ok": True})
                return
            self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})

    # support GET-style admin listings via a tiny JSON-RPC-ish endpoint
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            body = self.read_body()
            if path == "/api/admin/users":  # update user (households/admin flag)
                user = require_user(self)
                if not user.get("is_admin"):
                    raise AuthError("Admin only.")
                uname = body.get("username", "")
                users = get_users()
                target = next((u for u in users["users"]
                               if u["username"].lower() == uname.lower()), None)
                if not target:
                    raise ValueError("User not found.")
                if "is_admin" in body:
                    target["is_admin"] = bool(body["is_admin"])
                if isinstance(body.get("households"), list):
                    target["households"] = [slugify(h) for h in body["households"]]
                if body.get("password"):
                    if len(body["password"]) < 8:
                        raise ValueError("Password must be at least 8 characters.")
                    salt, ph = hash_password(body["password"])
                    target["password"] = f"{salt}${ph}"
                save_users(users)
                self.reply(200, {"ok": True})
            else:
                self.reply(404, {"error": "not found"})
        except AuthError as e:
            self.reply(401, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.reply(400, {"error": str(e)})


def migrate_flat_layout():
    """One-time move: old versions stored products.csv/inventory.csv directly
    in DATA_DIR. Move them into households/default/."""
    for fname in ("products.csv", "inventory.csv"):
        old = os.path.join(DATA_DIR, fname)
        if not os.path.exists(old):
            continue
        new = os.path.join(DATA_DIR, "households", "default", fname)
        os.makedirs(os.path.dirname(new), exist_ok=True)
        if os.path.exists(new):
            os.remove(old)          # household version wins
        else:
            os.replace(old, new)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    migrate_flat_layout()
    cfg = get_config()  # writes api_key on first run
    if user_count() == 0:
        print("No users yet — first visit will offer admin account setup.")
    print(f"Homepage widget key: {cfg['api_key']}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Food storage tracker UI: http://0.0.0.0:{PORT} "
          f"(data: {DATA_DIR}, config: {CONFIG_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()
