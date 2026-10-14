# v2.7 — Android app with barcode scanning

## Get for Android
- New **📱 Get for Android** button in the top-right corner of the site —
  downloads the official Android app straight from your own server
  (`/app.apk`, no external store or account needed).

## Android app
- On first launch you enter your server address (e.g.
  `https://eft.example.com`); the app then opens the tracker as a native
  app with its own icon, keeping you logged in.
- **Scan button (app only):** a 📷 button appears in the top bar when using
  the app. It opens the phone camera and scans barcodes (EAN-13/8, UPC-A/E,
  Code 128/39, ITF, QR).
  - Scanning a **mapped** barcode instantly selects the product in the
    "Record a purchase" form — check the date & quantity and press Buy.
  - Scanning an **unknown** barcode prompts global admins to map it right
    away (see below); other users are asked to contact a global admin.

## Barcodes tab (global admins)
- New **🏷 Barcodes** main tab (visible to global admins only) tying scanned
  barcode IDs to products in the global product list:
  - List of all mappings (barcode → product) with one-click removal.
  - "Map a barcode" form: type or scan a barcode ID, pick a product, press
    Map. Scanning an unknown code on your phone pre-fills the barcode for
    you.

## Notes
- The app requests camera permission the first time you scan.
- The APK is a self-signed, dependency-free WebView build; Android will ask
  you to allow installing from this source the first time.
