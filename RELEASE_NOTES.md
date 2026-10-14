# v2.7.2 — Android app: verify-build release + deep-link fallback

## Why your SSO still opened the browser
The v2.7.1 fix only takes effect once the **new APK is actually installed**
— the app on a phone keeps running the old build if the Docker image wasn't
re-pulled or Android kept the previous install. The old v2.7 build is the one
that hands Keycloak over to the browser.

## What's in 2.7.2
- **Version shown on the first-launch screen** ("App v2.7.2" under the Open
  button) so you can instantly confirm which build your phone is running.
  If it doesn't say 2.7.2, you're on the old app.
- **Deep-link fallback:** the app now accepts the custom redirect URI
  `win.strommingflix.eft://oidc/callback`. If an SSO login somehow ends up
  in the external browser, the phone bounces straight back into the app and
  finishes the login there (the code/state exchange happens server-side).
  Optional — only needed if you set this as the OIDC Redirect URI in
  Settings → Authentication (and register it in Keycloak).
- Same signing key as before, so it installs over an existing install.

## How to make sure you get the fixed app
1. Dockge: **Pull images → Deploy** (so `/app.apk` serves the new build).
2. On the phone: **uninstall** the old Food Tracker app.
3. Open the site in the phone browser → **📱 Get for Android** → install.
4. The first-launch screen must be readable (light text) and show
   **App v2.7.2**.
5. Log in with Keycloak — the login now happens inside the app and returns
   you there, logged in.
