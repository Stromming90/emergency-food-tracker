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
