# Emergency Food Storage Tracker

Track your emergency food storage: keep a permanent product list (with
manufacturer), record purchases with best-before dates, and see alerts at
**6 months**, **3 months** and **1 month** before each item expires.

Fully self-contained: the web server uses **only the Python standard
library** — no dependencies to audit or update. Runs anywhere Docker runs,
including TrueNAS.

## Features

- 📋 **Permanent product list** — name, manufacturer, category; extend any time
- 🛒 **Purchases** — per product + manufacturer, with best-before date & quantity
- ⏰ **Expiry alerts** — colour-coded badges: fine · <6 months · <3 months ·
  <1 month · expired (page auto-refreshes every minute)
- 👤 **User accounts** — first visit creates the admin account; sessions last
  7 days (PBKDF2-hashed passwords, HttpOnly cookies)
- 🏠 **Households** — separate inventories per household; users can belong
  to several and switch between them via the top bar dropdown
- 🌙 **Dark mode** — auto (follows your device), light or dark, per browser
- 🔑 **OIDC / SSO** — login via Keycloak (or any OIDC provider), optional
  auto-provisioning of unknown users, admin-by-email whitelist
- 📊 **gethomepage widget** — JSON API with API key showing expiry counts
- 💻 **CLI** — same data as the web app, handy for cron/scripts

## Run with Docker

```yaml
services:
  food-tracker:
    build:
      context: https://github.com/Stromming90/emergency-food-tracker.git
    container_name: food-tracker
    restart: unless-stopped
    ports:
      - "4500:8000"          # host:container
    volumes:
      - /mnt/apps-mirror/apps-data/emergency-food-tracker/config:/config
      - /mnt/apps-mirror/apps-data/emergency-food-tracker/data:/data
```

`docker compose up -d`, then open `http://<host>:4500`.

**First visit:** you're asked to create the **admin account** (and can name
your first household, e.g. "home"). After that, the login screen has a
username/password form (and an SSO button once OIDC is configured).

### Volumes

| Mount | Contents |
|---|---|
| `/data` | Household CSVs: `households/<name>/products.csv`, `households/<name>/inventory.csv` |
| `/config` | `users.json` (accounts), `config.json` (widget API key, OIDC settings) |

Your inventory lives in plain CSV files — a backup is just a copy of two
files per household. TrueNAS snapshot tasks on the data dataset work great.

> **Migration:** if you're upgrading from the pre-household version, the old
> `data/products.csv` / `data/inventory.csv` are moved automatically into
> `households/default/` on first start. Existing data is preserved.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Listen port inside the container |
| `DATA_DIR` | `/data` | Household data root |
| `CONFIG_DIR` | `/config` | Users & settings |
| `OIDC_ISSUER` | — | e.g. `https://keycloak.example/realms/home` |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | — | OIDC client credentials |
| `OIDC_ADMIN_EMAILS` | — | Comma-separated emails that become admin on SSO login |

OIDC can also be configured in the admin UI (⚙️) — the UI settings are
stored in `/config` and win over env vars only if set after startup.

### TrueNAS (SCALE)

1. Create datasets, e.g. `apps-mirror/apps-data/emergency-food-tracker/{config,data}`
2. Add the compose above via **Apps → Discover → Install via Compose**
   (or run it in Dockge: **+ Compose** → paste → Deploy)
3. Open `http://<truenas-ip>:4500`

## Admin panel (⚙️)

Visible to admins only:

- **Users** — create users (with password), toggle admin, assign households,
  delete users
- **Households** — create new households
- **OIDC / SSO** — issuer URL, client ID/secret, redirect URI (auto-detected
  if blank), admin emails, auto-create toggle
- **Homepage widget** — shows the API key for the widget endpoint

## OIDC / SSO (Keycloak)

1. In Keycloak, create a **confidential** client with *Standard Flow* enabled
2. Valid redirect URI: `http://<tracker-host>:4500/api/oidc/callback`
3. In the admin panel, set the issuer (realm URL), client ID and secret
4. Save — the "Log in with SSO" button appears on the login screen

Endpoints are discovered automatically from the issuer's
`/.well-known/openid-configuration`. With **auto-create** enabled (default),
unknown SSO users get a normal account on first login; list their emails in
*admin emails* to grant admin.

## gethomepage widget

Get your API key from the admin panel, then in homepage's `services.yaml`:

```yaml
- Food Storage:
    - Emergency Food Tracker:
        icon: mdi-food
        href: http://truenas:4500
        widget:
          type: customapi
          url: http://truenas:4500/api/widget?household=default&key=YOUR_API_KEY
          mapping:
            - field: expiring_within_1_month
              label: ≤1 month
            - field: expiring_within_3_months
              label: ≤3 months
            - field: expiring_within_6_months
              label: ≤6 months
            - field: expired
              label: expired
```

The endpoint (`GET /api/widget?household=<name>&key=<api_key>`) also returns
`next_expiries` (next 10 items with dates) and `alerts` (human-readable
strings) if you want richer mappings.

## CLI

```bash
python3 tracker.py add-product "Canned beans" --manufacturer "Example Foods" --category Canned
python3 tracker.py buy "Canned beans" 2028-06-01 --quantity 6
python3 tracker.py list-products
python3 tracker.py inventory            # sorted by best-before date
python3 tracker.py alerts               # current 6/3/1-month warnings
python3 tracker.py check                # print + desktop notification (cron)
```

Environment: `DATA_DIR` (data root, default `./data`) and `HOUSEHOLD`
(default `default`) — same files the web app uses.

```bash
HOUSEHOLD=cabin python3 tracker.py buy "Coffee" 2027-01-15 --quantity 2
```

## Data layout

```
data/
  households/
    <household>/products.csv     # name, manufacturer, category, added_date
    <household>/inventory.csv    # id, product, manufacturer, best_before, quantity, added_date
config/
  users.json                    # user accounts (PBKDF2-hashed passwords)
  config.json                   # widget API key, OIDC settings
```

## Security notes

- There is no HTTPS built in — put it behind your reverse proxy (TrueNAS /
  Traefik / nginx) before exposing it beyond localhost/LAN.
- The widget endpoint is authenticated by the API key only; treat it as
  semi-public (it exposes expiry dates, nothing personal).
- Sessions are in-memory: restarting the container logs everyone out.

## Development run (no Docker)

```bash
python3 server.py          # serves on :8000, data in ./data, config in ./config
```
