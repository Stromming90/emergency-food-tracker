# v2.8.0 — Barcode defaults + scan straight into inventory

## Swedish emergency-food barcode defaults
The tracker now ships with a bundled barcode reference list:
`data/barcode-defaults.json` — **1 747 Swedish grocery products** (pasta,
rice, canned fish, oils, honey, crispbread, coffee …) collected from Open
Food Facts and cleaned up (brand spellings, name casing, dedup).

On first start they are seeded automatically:
- products missing from your global product list are added (with type,
  category and size), existing products are never touched;
- their barcodes are mapped, so scanning any of them resolves instantly.

Seeding runs once; mappings you delete afterwards stay deleted.

## Scan items straight into the inventory (Android app)
The Household → **Inventory** section has its own **📷 Scan** button. It
opens a dedicated scanner that:
- resolves the scanned barcode to a product,
- asks for **how many** you're adding (quantity) and the best-before
  date (suggested from the product type's shelf life) — so you don't need
  to scan every single item,
- adds them to the inventory immediately, and offers **Scan another**
  for rapid stock-taking.

This is completely separate from the top-bar 📷 scan, which pre-fills the
*Record a purchase* form and maps unknown barcodes (global admin) — that
workflow is unchanged.

## Phone app
App version bumps to **2.8.0** (versionCode 31) in the source. The APK is
a thin WebView wrapper: the new inventory scan and the barcode defaults
arrive through the web UI the moment the server (Docker image) is updated
— **no APK reinstall is needed**. The downloadable APK remains the
unchanged 2.7.3 binary until the next wrapper rebuild
(`app-version.txt` still reports it honestly).

Web app version: 2.8.0.
