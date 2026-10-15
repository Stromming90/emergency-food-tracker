# v2.11.0 — One-tap push notifications, zero configuration

## Both old notification systems replaced by real Web Push
The in-app banner alerts (v2.10.1) and the ntfy / Gotify / Pushover
integration (v2.10.2) are gone. In their place: **standard Web Push
notifications** — the same technology big services use, built into
every modern browser.

- **No third-party apps, no accounts, no URLs, no tokens.** The server
  generates its own VAPID encryption keys automatically on first
  start; your browser's built-in push service handles delivery.
- **One tap to enable** on each device: Settings → Notifications →
  "Enable notifications on this device". Each user manages their own
  devices (no longer global-admin-only).
- **Alerts arrive on your phone's notification screen even when the
  app is closed.** The server checks all households about every six
  hours and pushes an alert when an item's status tag worsens
  ("Less than 6 months" → "Less than 3 months" → "Less than 1 month"
  → "Expired"). The first check only sets the baseline.
- **"Send test notification"** button to verify a device immediately.
- Expired subscriptions are pruned automatically (HTTP 404/410).

## Inside the APK app (WebView)
The Android WebView cannot receive Web Push (an OS limitation for any
wrapped site — it needs the browser's push infrastructure). Inside
the APK the Notifications tab says so; open the tracker in **Chrome or
Firefox on your phone** — or add it to your home screen — and enable
notifications there. They then arrive like any app's notifications,
even when the browser is closed. No reinstall is needed; the APK
binary is unchanged and is only re-named (`app-version.txt` → 2.11.0).

## Technical
- New endpoints: `GET /api/push/vapid`, `GET /api/push/status`,
  `POST /api/push/subscribe`, `POST /api/push/unsubscribe`,
  `POST /api/push/test`. Removed: `GET/POST /api/admin/push`,
  `POST /api/admin/push/test`.
- New file `static/sw.js` (service worker), served at `/sw.js` with
  `Service-Worker-Allowed: /`.
- The server is still **zero-dependency Python stdlib**: the required
  P-256 ECDH/ECDSA, HKDF and AES-128-GCM primitives are implemented
  in `server.py` itself, and validated at every startup against the
  FIPS-197 AES test vector and the complete RFC 8291 §5 example
  (plus OpenSSL cross-checks during development).
- Background check interval configurable via `PUSH_CHECK_SECONDS`
  (default 21600 = 6 h).

## Upgrade
`docker compose pull && docker compose up -d` — then tap "Enable
notifications on this device" in Settings → Notifications on each
device.
