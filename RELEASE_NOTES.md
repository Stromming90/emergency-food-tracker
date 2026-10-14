# v2.7.3 — Verifiable APK download

## Versioned download filename
- The **Get for Android** download is now named
  `emergency-food-tracker-2.7.3.apk` (previously the fixed name
  `emergency-food-tracker.apk`, which let Android silently re-open an
  older download). If the file on your phone doesn't carry **2.7.3** in
  its name, it is not this build — delete old downloads and re-download.
- The APK is served with `Cache-Control: no-store` so neither the phone
  browser nor a proxy can hand back a stale copy.

## Reminder (app fixes are in the APK since 2.7.1/2.7.2)
- SSO/Keycloak login stays inside the app and returns you to it.
- Setup screen has light text on the dark background and shows
  **App v2.7.3** under the Open button — check it after installing.
- App versionCode 30, signed with the same key as all 2.7.x builds, so it
  installs over an existing install.
