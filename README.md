# Emergency Food Storage Tracker

> **Disclaimer:** this repository is entirely *vibe-coded* — designed, written and maintained through conversations with [Mistral AI](https://mistral.ai), not hand-written code.

Track your emergency food storage: keep a permanent product list, record purchases with best-before dates, and see alerts at
different intervals before each item expires.

Fully self-contained: the web server uses **only the Python standard library** — no dependencies to audit or update. Runs anywhere Docker runs, including TrueNAS.

## Features

- 📋 **Global product list** — the list is shared by all households. 
- 🏷 **Barcode reference lists** (v2.8) — the tracker ships with a bundled list of Swedish emergency-food products. Additional lists can be added in the future.
- 🏠 **Households** — separate inventories per household; users can belong to several and switch between them.
- 🌙 **Dark mode** — for your comfort.
- 🔑 **OIDC / SSO** — login via Keycloak, Authentik or Authelia (or any OIDC provider).
- 📊 **gethomepage widget** — JSON API with a personal API key showing expiry counts, per household or across all households.

## Run with Docker

The project publishes a prebuilt image to GitHub Container Registry — every push to `main` triggers a GitHub Actions build automatically (see `.github/workflows/docker-publish.yml`). The image is tagged `latest` and with the current release version (e.g. `v2.8.0`).

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

Adjust the volume paths to your host. `docker compose up -d`, then open `http://<host>:4500`.

If you prefer building from source instead of the registry image, replace
`image:` with:

```yaml
    build:
      context: https://github.com/Stromming90/emergency-food-tracker.git
```

— and rebuild with `docker compose build --pull --no-cache` on updates.

### Getting started

**First visit:** you're asked to create the **global admin account** and your **first household** — name it something like "home". 
After that, the login screen has a username/password form (and an SSO button once OIDC is configured). 

The bundled Swedish barcode defaults are seeded on first start; they appear in the Products tab and the Barcodes tab (global admin).

Other users are created in Settings → Users (by a global admin, or by a household admin for their own households). 
Any user can create additional households in Settings → Households — the creator automatically becomes the household admin of the new household.

### Volumes

| Mount | Contents |
|---|---|
| `/data` | `products.csv` (global product list), `households/<name>/inventory.csv` (holds the household inventory |
| `/config` | `users.json` (accounts, roles, API keys), `config.json` (OIDC settings, barcode mappings) |

Your data lives in plain CSV/JSON files — a backup is just a copy of the folder. TrueNAS snapshot tasks on the data dataset work great.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `4500` | Listen port inside the container |
| `DATA_DIR` | `/data` | Data root |
| `CONFIG_DIR` | `/config` | Users & settings |
| `OIDC_ISSUER` | — | e.g. `https://keycloak.example/realms/home` |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | — | OIDC client credentials |
| `OIDC_ADMIN_EMAILS` | — | Comma-separated emails that become global admin on SSO login |

OIDC can also be configured in the settings UI (⚙️) — the UI settings are stored in `/config` and win over env vars only if set after startup.

### TrueNAS (SCALE)

1. Create datasets, e.g. `apps-data/emergency-food-tracker/{config,data}`
2. Add the compose above via **Apps → Discover → Install via Compose** (or run it in Dockge: **+ Compose** → paste → Deploy)
3. Open `http://<truenas-ip>:4500`

## Roles

- **Global admin** — the general admin role for the application with access to do and see everything.
- **Household admin** — can edit the product list, migrate inventory between households and manage users of the households.
- **User** — records purchases and manages the inventory of their own households; can create new households (becoming that household's admin) and has a personal API key.

## gethomepage widget

Get your personal API key from Settings → API Key, then in homepage's
`services.yaml`:

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

- `household=all` — all households you have access to (default)
- `household=default` — a single household (use the slug, e.g. lowercase)
- `household=home,cabin` — a comma-separated list of households

Each user has their own unique API key (regenerable in Settings → API
Key); the widget only reports the households that user has access to.
Global admins see all households.

### Response fields

| Field | Meaning |
|---|---|
| `total_items` | **Total quantity** of all items (sum of quantities — the actual number of cans/units in stock) |
| `total_quantity` | Alias for `total_items` |
| `total_entries` | Number of distinct inventory rows (entries), regardless of quantity |
| `expiring_within_1_month` / `_3_months` / `_6_months` | Count of items whose **most urgent** warning level falls in that bucket — an item 2 months from expiry is counted *only* in "Less than 3 months", not in 6 |
| `expired` | Items past their best-before date |
| `attention` | Items needing attention (expired or ≤6 months) |
| `per_household` | Breakdown per household |
| `next_expiries` | Next 10 items with product, best-before date, days left and level |
| `alerts` | Human-readable alert strings, one per item |

## OIDC / SSO

### Keycloak

1. Create a **confidential** client with *Standard Flow* enabled
2. Valid redirect URI: `http://<tracker-host>:4500/api/oidc/callback`
3. In Settings → Authentication, set the issuer (realm URL, e.g.
   `https://keycloak.example/realms/home`), client ID and secret
4. Save — the "Log in with SSO" button appears on the login screen

### Authentik

1. Create a new **OAuth2 provider**; under *Protocol settings* choose
   *Authorization code* flow
2. Redirect URI / Origins: `http://<tracker-host>:4500/api/oidc/callback`
3. Note the **Client ID** and **Client secret**
4. In Settings → Authentication, set the issuer to your Authentik
   application's *OpenID Configuration Issuer`
   (e.g. `https://authentik.example/application/o/<app-slug>/`), plus the
   client ID and secret

### Authelia

1. In your `configuration.yml`, add an `oauth2` section under the
   tracker's client:

```yaml
      - client_id: food-tracker
        client_secret: <secret>
        public: false
        authorization_code: 60
        redirect_uris:
          - http://<tracker-host>:4500/api/oidc/callback
        scopes:
          - openid
          - profile
          - email
        userinfo_signed_signature_alg: none
        token_endpoint_auth_method: client_secret_basic
```

2. In Settings → Authentication, set the issuer to your Authelia instance's OIDC issuer (e.g. `https://auth.example`), plus the client ID and secret

Endpoints are discovered automatically from the issuer's `/.well-known/openid-configuration` for all providers. With **auto-create** enabled (default), unknown SSO users get a normal account on first login; list their emails in *Global admin emails* to grant the global admin role.

## Data layout

```
data/
  barcode-defaults.json        # bundled Swedish barcode defaults (v2.8, read-only)
  products.csv                  # GLOBAL product list (name, manufacturer, type, category, size)
  households/
    <household>/inventory.csv   # id, product, manufacturer, best_before, quantity, added_date
config/
  users.json                    # user accounts (roles, household admin rights, personal API keys)
  config.json                   # OIDC settings + barcode -> product mappings
```

## Security notes

- There is no HTTPS built in — put it behind your reverse proxy (TrueNAS /
  Traefik / nginx) before exposing it beyond localhost/LAN.
- The widget endpoint is authenticated by the API key only; treat it as
  semi-public (it exposes expiry dates, nothing personal).
- Sessions are in-memory: restarting the container logs everyone out.
