# Android app (source)

The APK shipped as `../eft-app.apk.b64` is built from this directory — a
minimal WebView wrapper around the web UI, built **without Gradle**:

- `java/win/strommingflix/eft/MainActivity.java` — WebView activity:
  asks for the server URL on first launch, stores it, keeps cookies,
  grants the WebView camera access (needed for barcode scanning).
- `AndroidManifest.xml` — package `win.strommingflix.eft`, INTERNET +
  CAMERA permissions, minSdk 24, versionCode 31 (app v2.8.0).
- `gen_icons.py` — regenerates the launcher icons (`res/mipmap-*`),
  pure Python stdlib, run `python3 gen_icons.py`.
- `build.sh` — full build: `aapt2 compile/link` → `javac` → `d8` →
  `zipalign` → `apksigner`, then base64-encodes the APK into
  `../eft-app.apk.b64`. Signs with `debug.keystore` (restored from the
  committed `debug.keystore.b64` so future updates install over the
  existing app; password `android`).

## Building

Requirements: any JDK 17+ and Android SDK build-tools 34 + platform
android-34 on disk. Set the three paths at the top of `build.sh`, then:

```sh
python3 gen_icons.py
bash build.sh
```

The web app detects the wrapper via the `EFT-Android/2.8` user-agent
token (appended by the WebView) and then shows the scan buttons: the
top-bar 📷 scan (pre-fills a purchase / maps barcodes) and the separate
Inventory 📷 scan (v2.8 — adds scanned items with a quantity straight
into the household inventory). Because the app is a thin WebView
wrapper, new web features like the inventory scan appear without
reinstalling the APK.
