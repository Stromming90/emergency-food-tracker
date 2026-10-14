# v2.7.4 — Cache-proof APK download

## Why the phone still downloaded the old APK
Every download used the same URL (`/app.apk`), so a cache between the phone
and the server (browser cache / Cloudflare / proxy) could hand back the stale
response from before the update — which is why the PC got the new versioned
file while the phone did not.

## What's fixed
- The **Get for Android** button now points at a **versioned URL**:
  `/app-2.7.3.apk`. A unique URL per app version cannot be served from any
  cache — the phone always gets the real current file.
- The page fetches the current app version from `/app-version.txt`
  (uncached) and rewrites the download link on every login, so the link
  always matches the bundled app.
- The old `/app.apk` URL still works (with the versioned filename and
  `no-store`), for anything that kept the old link.

The app binary itself is unchanged from 2.7.3 (App v2.7.3, versionCode 30).
Web app version: 2.7.4.
