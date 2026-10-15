# v2.10.1 — Barcodes merged into Products, phone notifications fixed

## Mobile app
- **Notifications now work in the phone app.** The Android WebView
  never grants the browser notification permission — that is why the
  toggle could not be enabled. In the app, alerts now appear as an
  **in-app banner** (with vibration), no permission needed. In normal
  browsers the behaviour is unchanged, with the banner as a fallback if
  permission is missing.
- The downloadable APK is always named after the current version — with
  this update it is served as **emergency-food-tracker-2.10.1.apk** —
  even though the app binary is unchanged. The app is a thin WebView
  wrapper: every fix below arrives through the web UI the moment the
  server is updated, so **no reinstall is needed**.

## Products & Barcodes merged
The separate **Barcodes** tab is gone — the Products tab now holds all
barcode functionality in one place:
- The product list has a new **Barcode** column, with its own
  per-column filter. Every product shows the barcodes mapped to it.
- In **✏️ Edit** mode (global admin), each barcode gets a ✕ to remove
  it, and each product row gets a **＋** to add a barcode.
- **Add a product** keeps its barcode field, and the product scanner
  still pre-fills it for unknown barcodes.
- The **country barcode list import** (previously in Settings →
  Barcodes) is now a card at the bottom of the Products tab: pick a
  country list (e.g. Sweden, 1 747 scanned products) and add it with a
  confirmation. Imports still run once per country, additively.
- The Settings → Barcodes tab has been removed.

No data changed: existing barcode mappings and the Sweden list (if
already imported) are all still there — they now show up in the
product list's Barcode column.

Web app version: 2.10.1.
