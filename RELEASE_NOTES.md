# v2.12.2 — Fix: the update button did nothing on the old app

## What was wrong
On a phone still running app **v2.12.0**, tapping "⬇ Download update"
looked dead: that app version has no download handler, and the
behind-the-scenes `intent://` URL used to bounce you to the browser
was silently swallowed on some devices.

## What happens now
- Tapping **Download** in the old app opens a **"Get the app update"**
  dialog with two buttons:
  - **Open in Chrome** — targets Chrome explicitly.
  - **Open in your browser** — generic browser intent.
  Both use a real link click, which old WebViews handle far more
  reliably than a JavaScript redirect.
- If a browser still does not open, the dialog shows the **server
  address to type into any browser**, with the exact clicks spelled
  out (Settings ⚙️ → About → ⬇ Download).
- Apps on v2.12.1+ keep the one-tap in-app download; browsers keep the
  direct download. **The APK is unchanged (2.12.1) — this is a web UI
  fix, so `docker compose pull && docker compose up -d` is all you
  need.**

# v2.12.1 — Download the app from the web & update it from inside the app

## Find the app from the website
- **Settings → About** now exists: server/app version info and a big
  **Download Android app** button (serves the current APK from
  `/app.apk`, always the latest version built by CI).
- Android **browsers** (not the app) get a dismissible banner under
  the header: "Get the Android app" with a one-tap Download button.

## Update the app from inside the app
- Every time the app opens, it compares its own version (the
  `EFT-Android/<version>` user-agent token) with the APK version
  bundled on the server (`/app-version.txt`). When the server has a
  newer one, a **"App update available"** banner appears at the top
  with a Download button — also in Settings → About.
- The app update (v2.12.1) handles the download **in-app** through the
  system download manager: tap the notification when it finishes and
  Android opens the installer. Installs over the current app (same
  signing key) — server address, session and settings are kept.
- The currently installed v2.12.0 app has no download handler, so on
  that version the download link opens the **browser**, which
  downloads and installs the APK the normal way.

# v2.12.0 — Notifications from the Android app itself

## Native notifications in the APK app
The Android app now delivers **real system notifications on its own** —
no browser needed, no third-party apps, nothing to configure:

- After updating, the app asks once for the notification permission
  and then runs a background check about every 30 minutes (also after
  a phone reboot).
- When an item's status tag worsens ("Less than 6 months" → "Less than
  3 months" → "Less than 1 month" → "Expired"), the app raises a
  native notification **even when the app is closed**. The first
  background check only sets the baseline, so you are not flooded with
  alerts right after installing the update.
- Each poll refreshes your login session, so the app keeps working in
  the background without you having to log in again. (If you restart
  the *server*, open the app once to log in again.)
- The new APK is signed with the same key as before — it installs
  right over the existing app and keeps your server address and
  settings.

## How it works
- New server endpoint: `GET /api/push/inbox?device=<uuid>` — returns
  the alerts for the households you can see since that device's last
  poll. Devices auto-register on first poll and are pruned after 90
  days of silence. The browser Web Push system from v2.11.0 is
  unchanged and keeps working for browser/home-screen installs.
- The APK is now rebuilt automatically by CI (`app/src` → `build.sh`,
  no Gradle); the web UI's Notifications tab explains this inside the
  app.

## Upgrade
1. `docker compose pull && docker compose up -d`
2. Download the updated app from Settings → About (or `/app-2.12.0.apk`)
   and install it over the old one — then tap "Allow" when it asks for
   the notification permission. Done.
