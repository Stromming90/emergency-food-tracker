# Emergency Food Storage Tracker

Track your emergency food storage: keep a permanent product list (with
manufacturer), record purchases with best-before dates, and see alerts at
**6 months**, **3 months** and **1 month** before each item expires.

Fully self-contained: the web server uses **only the Python standard
library** — no dependencies to audit or update. Runs anywhere Docker runs,
including TrueNAS.

## Features

- 📋 **Global product list** — name, manufacturer, category; extend any time.
  The list is shared by **all households**: a product added by one household
  is immediately available to everyone.
- ✏️ **Admin product editing** — admins can rename/update any product on the
  list (✎ button); the change propagates to every household's inventory.
- 🛒 **Purchases** — per product + manufacturer, with best-before date & quantity
- ⏰ **Expiry alerts** — colour-coded badges: fine · Less than 6 months ·
  Less than 3 months · Less than 1 month · expired (page auto-refreshes every
  minute). Each item shows only its **most urgent** warning level.
- 👤 **User accounts** — first visit creates the admin account; sessions last
  7 days (PBKDF2-hashed passwords, HttpOnly cookies)
- 🏠 **Households** — separate inventories per household; users can belong
  to several and switch between them via the top bar dropdown. Inventories
  can be **migrated** to other households (Settings → Households).
- 🌙 **Dark mode** — auto (follows your device), light or dark, per browser
- 🔑 **OIDC / SSO** — login via Keycloak (or any OIDC provider), optional
  auto-provisioning of unknown users, admin-by-email whitelist
- 📊 **gethomepage widget** — JSON API with API key showing expiry counts,
  per household or across all households
- 💻 **CLI** — same data as the web app, handy for cron/scripts

## Run with Docker

The project publishes a prebuilt image to GitHub Container Registry —
every push to `main` triggers a GitHub Actions build automatically
(see `.github/workflows/docker-publish.yml`).

```yaml
services:
  food-tracker:
    image: ghcr.io/stromming90/emergency-food-tracker:latest
    container_name: food-tracker
    restart: unless-stopped
    ports:
      - "4500:4500"
    environment:
      - PORT=4500
    volumes:
      - /mnt/apps/emergency-food-tracker/config:/config
      - /mnt/apps/emergency-food-tracker/data:/data
```

Adjust the volume paths to your host. `docker compose up -d`, then open
`http://<host>:4500`.

### Updating to a new version

Because the app runs from a prebuilt image, updating is the same as with any
Docker app — no rebuild from source:

```bash
docker compose pull && docker compose up -d
```

In Dockge: open the stack → **Pull images** (or edit → **Deploy**) and the
new version is fetched and started. Your data in `/data` and `/config` is
untouched.

> The GHCR package must be **public** for the host to pull it without
> logging in. After the first successful Actions run, go to your GitHub
> profile → **Packages** → `emergency-food-tracker` → **Package settings**
> → **Change visibility** → Public. (Alternatively `docker login ghcr.io`
> with a GitHub token on the host for private packages.)

If you prefer building from source instead of the registry image, replace
`image:` with:

```yaml
    build:
      context: https://github.com/Stromming90/emergency-food-tracker.git
```

— and rebuild with `docker compose build --pull --no-cache` on updates.

**First visit:** you're asked to create the **admin account** (and can name
your first household, e.g. "home"). After that, the login screen has a
username/password form (and an SSO button once OIDC is configured).

### Volumes

| Mount | Contents |
|---|---|
| `/data` | `products.csv` (global product list), `households/<name>/inventory.csv` |
| `/config` | `users.json` (accounts), `config.json` (widget API key, OIDC settings) |

Your data lives in plain CSV files — a backup is just a copy of the folder.
TrueNAS snapshot tasks on the data dataset work great.

> **Migration:** upgrading from an older version is automatic on first
> start — the flat pre-household layout moves into `households/default/`,
> and v2.0 per-household product lists are merged into the new global
> `products.csv`. Existing data is preserved.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `4500` | Listen port inside the container |
| `DATA_DIR` | `/data` | Data root |
| `CONFIG_DIR` | `/config` | Users & settings |
| `OIDC_ISSUER` | — | e.g. `https://keycloak.example/realms/home` |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | — | OIDC client credentials |
| `OIDC_ADMIN_EMAILS` | — | Comma-separated emails that become admin on SSO login |

OIDC can also be configured in the settings UI (⚙️) — the UI settings are
stored in `/config` and win over env vars only if set after startup.

### TrueNAS (SCALE)

1. Create datasets, e.g. `apps-data/emergency-food-tracker/{config,data}`
2. Add the compose above via **Apps → Discover → Install via Compose**
   (or run it in Dockge: **+ Compose** → paste → Deploy)
3. Open `http://<truenas-ip>:4500`

## Settings (⚙️)

Visible to admins only, organised in tabs:

- **Users** — create users (with password and household checkboxes), toggle
  admin, edit a user's households via checkboxes, delete users
- **Households** — create households (optionally assigning existing users
  from a checkbox list), delete households, and **migrate inventory**
  (move all items from one household to another)
- **Authentication** — OIDC / SSO: issuer URL, client ID/secret, redirect
  URI (auto-detected if blank), admin emails, auto-create toggle
- **API key** — the API key for the gethomepage widget endpoint

## OIDC / SSO (Keycloak)

1. In Keycloak, create a **confidential** client with *Standard Flow* enabled
2. Valid redirect URI: `http://<tracker-host>:4500/api/oidc/callback`
3. In Settings → Authentication, set the issuer (realm URL), client ID and secret
4. Save — the "Log in with SSO" button appears on the login screen

Endpoints are discovered automatically from the issuer's
`/.well-known/openid-configuration`. With **auto-create** enabled (default),
unknown SSO users get a normal account on first login; list their emails in
*admin emails* to grant admin.

## gethomepage widget

Get your API key from Settings → API key, then in homepage's `services.yaml`:

```yaml
- Food Storage:
    - Emergency Food Tracker:
        icon: mdi-food
        href: http://192.168.x.x:4500
        widget:
          type: customapi
          url: "http://192.168.x.x:4500/api/widget?household=all&key=YOUR_API_KEY"
          mappings:
            - field: total_items
              label: "Total items"
            - field: expiring_within_1_month
              label: "Less than 1 month"
            - field: expiring_within_3_months
              label: "Less than 3 months"
            - field: expiring_within_6_months
              label: "Less than 6 months"
            - field: expired
              label: "Expired"
```

### Household selection

The `household` query parameter controls which inventories are counted:

- `household=all` — all households (default)
- `household=default` — a single household (use the slug, e.g. lowercase)
- `household=home,cabin` — a comma-separated list of households

### Response fields

| Field | Meaning |
|---|---|
| `total_items` | Number of distinct inventory entries across the selected households |
| `total_quantity` | Sum of all quantities |
| `expiring_within_1_month` / `_3_months` / `_6_months` | Count of items whose **most urgent** warning level falls in that bucket — an item 2 months from expiry is counted *only* in "Less than 3 months", not in 6 |
| `expired` | Items past their best-before date |
| `attention` | Items needing attention (expired or ≤6 months) |
| `per_household` | Breakdown per household |
| `next_expiries` | Next 10 items with product, best-before date, days left and level |
| `alerts` | Human-readable alert strings, one per item |

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
(default `default`) — same files the web app uses. The product list is
global; only inventories are per household.

```bash
HOUSEHOLD=cabin python3 tracker.py buy "Coffee" 2027-01-15 --quantity 2
```

## Data layout

```
data/
  products.csv                  # GLOBAL product list (shared by all households)
  households/
    <household>/inventory.csv   # id, product, manufacturer, best_before, quantity, added_date
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
python3 server.py          # serves on the PORT env (default 4500), data in ./data, config in ./config
```
