# v3.0.0 — Country lists as CSVs, edit-mode locking, notifications for web users

## Country barcode lists (Products tab)
- Lists now live as **individual CSV files** in the folder
  `data/barcode-countries/` (header:
  `barcode,name,manufacturer,type,category,size`). The old single
  `barcode-defaults.json` is migrated automatically on first start.
- **Nothing is added to the product list automatically** — a list only
  reaches your product list when you import it with
  **"Add list to products"** (manual, once per list).
- Global admins can now:
  - **Download a country list** as CSV ("⬇ Download CSV"),
  - **Add a new country list** or **update an existing one** by
    uploading a CSV ("⬆ Add / update list"),
  - **Export the product list** (with barcodes) as CSV
    ("⬇ Export CSV" in the Product list toolbar).

## Product list editing
- **All editing is now locked behind the ✏️ Edit button.** The
  per-product edit (✎) and remove (✕) buttons, and the
  "Add a product" form, only appear in Edit mode.
- Removed the per-product "remove barcode" (✕) and "add barcode" (＋)
  buttons from the list — the Barcode column is read-only.
- ✎ **Edit product** edits every product variable: type, category,
  name, manufacturer and size.
- New **🗑 Clear list** button (Edit mode) removes the entire product
  list at once. It refuses while products are still in an inventory
  (inventory is never touched) and clears barcode mappings.

## Notifications
- Browser (phone-web) notifications are back: **Enable / Disable /
  Send test notification** for the browser push service (v2.11
  mechanics, server checks about every six hours). These buttons are
  hidden inside the Android app.
- The Android app's **🔔 Test native notification** and
  **Open notification settings** are hidden for browser users.

## Android app
- No app update in this release — the app is a WebView wrapper, so all
  of the above arrives in the app after a server update. In the app,
  Settings → About now shows the **current version** the UI is running
  (v3.0.0) even though the APK wrapper itself is unchanged (2.12.6).

# v2.12.8 — Cleanup: notifications tab + About tab

## Notifications tab
- Removed "Enable notifications on this device", "Disable on this
  device" and "Send test notification" (browser web-push buttons —
  they never worked inside the Android app, which has no push
  service). Kept the buttons that work: "🔔 Test native notification"
  and "Open notification settings".
- The section text now describes the actual behaviour: a background
  check about every 30 minutes (plus one right after the app opens)
  that raises a system notification when items change status tag.

## About tab
- When the installed app is the latest version, the download button
  is hidden (nothing to download).
- Removed the "Download this update…" explanation text and the
  "The APK installs over…" paragraph.

Server-only change (v2.12.8); no app update needed — the app ships
this UI from the server.

# v2.12.7 — Fix: "Last check: HTTP 401" + silent test button (app 2.12.6)

## What was wrong
The background check itself worked (permission granted, job
scheduled), but the status line showed "Last check: HTTP 401":
the poll had run while the session cookie was expired/logged out,
and the app then waited up to 30 minutes before trying again —
so the user never saw a successful check. The test button also
produced nothing: it raised the notification from the WebView's
bridge thread without any visible feedback when it failed.

## What is fixed (app 2.12.6)
- A poll now runs **immediately every time the app opens** (new
  `EFTNative.pollNow()` bridge, called by the web UI at startup).
  After a login, the very next app open re-polls with the fresh
  cookie — the 401 state clears itself.
- The test button and pollNow post to the main thread and show a
  toast for success ("Test notification sent — check the
  notification shade") and for failure — plus the crash log —
  so nothing fails silently anymore.
- The web UI explains a stale 401 result ("the last check ran
  while logged out — reopen the app to refresh it").

## Upgrade
Update the server (docker compose pull && up -d), then update the
app from Settings → About → Download. The old crash report in the
dialog is stale — tap Dismiss.

# v2.12.6 — Fix: background job still not scheduled (app 2.12.5)

## What was wrong (from the crash report dialog)
The Android 16 crash report showed:
`SecurityException: android.permission.ACCESS_NETWORK_STATE required
for jobs with a connectivity constraint`. JobScheduler silently
requires this permission for the network constraint the notification
job uses — the manifest did not declare it, so **no background job was
ever scheduled** on that device (this time it was caught and recorded
instead of crashing the app — that is why the app kept working).
Also, the update dialog's Chrome/browser buttons did nothing: the
`intent://` anchor-click trick is not honoured by that WebView.

## What is fixed (app 2.12.5)
- `ACCESS_NETWORK_STATE` added to the manifest — the background
  notification job now schedules for real. All permission
  requirements of the job are now declared
  (RECEIVE_BOOT_COMPLETED + ACCESS_NETWORK_STATE).
- Browser buttons in the update dialog now call the app's native
  bridge (`EFTNative.openUrl`) — a real ACTION_VIEW outside the
  WebView — and every failure shows a visible toast. The old
  intent:// path stays only as a fallback for older app versions.
- "Open notification settings" falls back to the app details page if
  the direct notification settings screen is unavailable.

## Update
`docker compose pull && docker compose up -d`, then in the app:
Settings ⚙️ → About → ⬇ Download → **⬇ Download in app** (the app
downloads and opens the installer itself), or **🌐 Download in Chrome**
/ **Download in your browser** — these now open a real browser. After
installing, check Settings ⚙️ → Notifications: it should say
"Permission: allowed ✓ · Background job: scheduled ✓".

# v2.12.5 — Fix: in-app update download did nothing (app 2.12.4)

## What was wrong
Tapping "Download update" inside the app did nothing. The app handed
the download to the system DownloadManager — which silently failed on
at least one real device (Android 16). The phone therefore stayed on
app 2.12.2, whose recorded crash report (shown in the crash dialog)
confirmed the missing RECEIVE_BOOT_COMPLETED permission — already fixed
in 2.12.3, but impossible to install because the download itself was
broken.

## What is fixed (app 2.12.4)
- **The app downloads the update itself**: plain HTTP into its own
  storage, then straight into the Android package installer via a
  bundled content provider — no DownloadManager involved. The system
  asks once for permission to let the app install updates; approve it.
- The outcome is **visible**: a toast while downloading, a toast with
  the result, and "Last update download: ok (N bytes)" in Settings ⚙️ →
  Notifications. Failures also land in the crash report dialog.
- The update dialog now opens for **every** app version: "⬇ Download in
  app" (2.12.4+), plus **Download in Chrome** / **in your browser**
  fallback buttons and the manual address — so there is always a
  working path, and nothing can fail silently.

## Update
`docker compose pull && docker compose up -d`, then in the app:
Settings ⚙️ → About → ⬇ Download → **Download in Chrome** (this one
download goes through the browser), tap the downloaded APK, install.
From 2.12.4 on, all future updates install fully in-app.

# v2.12.4 — Fix: native app notifications never started (app 2.12.3)

## What was wrong
After enabling notifications in the app, nothing arrived. **Root
cause**: the app schedules its background check as a *persisted*
JobScheduler job — and Android requires the `RECEIVE_BOOT_COMPLETED`
permission for persisted jobs. The manifest did not declare it, so
Android rejected the schedule: no background job ever existed, so no
notifications were ever raised. (This was also the true root cause of
the earlier "app closes on open" crash — in app 2.12.0 the same
exception was uncaught and killed the app; the 2.12.2 fix stopped the
crash but left the failure silent.)

## What is fixed (app 2.12.3)
- `RECEIVE_BOOT_COMPLETED` added to the manifest — the background job
  now schedules successfully and survives reboots.
- A scheduling failure now shows a toast instead of dying silently.
- **New: real status & controls in the app.** Settings ⚙️ →
  Notifications now shows the actual native state — permission
  allowed?, background job scheduled?, when the last background check
  ran and what it returned — plus two buttons:
  - **🔔 Test native notification** — raises a real system
    notification immediately, so you can verify end to end.
  - **Open notification settings** — jumps straight to the app's
    notification settings if the permission was denied.

## Update
`docker compose pull && docker compose up -d`, then Settings ⚙️ →
About → ⬇ Download in the app (2.12.3+) — installs over the current
app. Then check Settings ⚙️ → Notifications: it should say
"Permission: allowed ✓ · Background job: scheduled ✓", and the test
button should pop a notification.

# v2.12.3 — Fix: app crashed and could not be reopened (app 2.12.2)

## What was wrong
Right after installing the update and accepting the notification
permission, the app would close — and from then on it could not be
opened at all; reinstalling did not help.

**Root cause**: the background notification job (PollJobService,
running inside the app's own process) read the WebView session cookie
from its worker thread. On some devices that throws an *Error* (a
native WebView failure), which the `catch (Exception)` block could not
intercept — the error killed the whole app process. Because the job is
**persisted**, Android re-delivers it the moment the app process
starts: open app → job fires → process dies. That is the crash loop,
and reinstalling does not clear a persisted job.

## What is fixed (app 2.12.2, served from this release)
- The session cookie is now read on the **main thread** (inside
  onStartJob, where it is legal) and only the HTTP request runs on the
  background thread.
- The entire job now catches `Throwable` and records it instead of ever
  crashing the process — the job physically cannot kill the app again.
- The notification/job scheduling in MainActivity is also guarded.
- **New: crash reporting.** If anything ever crashes the app again,
  the stack trace is saved and shown on the next launch with a
  **Copy report** button — so it can be pasted into a bug report
  without USB debugging.

Server code is unchanged (version bump only): update with
`docker compose pull && docker compose up -d`, then download the new
app APK from a browser on the phone (the site → Settings ⚙️ → About →
⬇ Download) and install it over the broken one — same signing key.

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
