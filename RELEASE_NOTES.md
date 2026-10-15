# v2.10.2 — Hotfix: real push notifications, even when the app is closed

## Push notifications to your phone (server-side)
The v2.10.1 alerts only appeared inside the app while it was open. This
hotfix adds **true push notifications**:

- A background checker on the **server** scans every household about
  **every six hours** and pushes an alert when any item changes status
  tag — "Less than 6 months", "Less than 3 months", "Less than 1
  month" or "Expired".
- Pushes arrive on your phone's notification screen **even when the
  app is not open** — no app changes needed, the WebView wrapper stays
  as it is.
- Alerts are delivered through the push service of your choice, set up
  in **Settings → Notifications → Push notifications (server)**
  (global admin only):
  - **ntfy** (recommended, free & open source): install the
    [ntfy app](https://ntfy.sh), pick a secret topic, subscribe to it
    on your phone and paste the topic URL (e.g.
    `https://ntfy.sh/my-secret-topic`) into the tracker.
  - **Gotify**: paste your Gotify server URL and an application token.
  - **Pushover**: paste your app token and user key from pushover.net.
- **Send test push** verifies the setup immediately; the first regular
  check establishes the baseline, and alerts start from the next
  status change.
- The in-app banner alerts from v2.10.1 remain for when the app is
  open. The server URL field also accepts a self-hosted ntfy server.

## Mobile app
The downloadable APK is always named after the current version — with
this update it is served as **emergency-food-tracker-2.10.2.apk** —
even though the app binary is unchanged. The app is a thin WebView
wrapper: this hotfix arrives through the web UI the moment the server
is updated, so **no reinstall is needed**. (The push notifications are
sent by the server to the ntfy/Gotify/Pushover app on your phone,
which is why they work without touching the WebView app at all.)

Web app version: 2.10.2.
