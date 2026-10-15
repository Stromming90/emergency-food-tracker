# v2.9.0 — Barcode country lists, per-column filters, storage guide

## Barcodes
- **Country lists, opt-in**: the barcode reference list now starts empty.
  A global admin imports the bundled **Sweden** list (1 747 scanned
  grocery products) in **Settings → Barcodes** — "Use the below dropdown
  menu to add a pre-existing list of scanned barcodes, sorted by country
  of purchase" — with a confirmation before anything is added. Each list
  is imported once; products that already exist are not duplicated, and
  mappings you delete afterwards stay deleted.
- **Barcodes tab reworked**: the "Map barcode" form is gone. Removing or
  adding mappings is now behind an **Edit button** (global admin) with
  buffered changes and a **Confirm changes** button. The list shows
  barcode, product, brand and size in separate, filterable columns.
- Sizes that were baked into product names (e.g. "Fusilli Fullkorn
  500g") are cleaned up and live only in the size field.

## Household
- **Record a purchase**: new **Category** filter between Type and
  Product; the product dropdown now also shows the size.
- The **Scan** button moved from the Inventory section to *Record a
  purchase* (it still adds scanned items straight into the inventory,
  with quantity, separate from the product-list scan).
- **Inventory list**: a text filter per column — filter on several
  things at once.

## Products
- **Add a product** has a **Barcode** field, and its own **Scan**
  button (moved here from the top bar). Scanning a barcode that isn't on
  the list pre-fills the form with the barcode and prompts you to
  continue adding the information.
- **Size** is now free text and accepts "/", e.g. **"500/350 g"**.
- **Product list**: a text filter per column.

## Information
- New **storage & shelf life** table for the 30 most common emergency
  foods — consistent **months** throughout, plus notes on which foods
  (white rice, honey, sugar, canned goods …) stay good long beyond
  their "best before" date.

## Mobile app
- The "Get for Android" phone-app button is removed from the app UI —
  the app is a thin WebView wrapper, so every update arrives with the
  server and no APK reinstall is needed. `app-version.txt` still tracks
  the version (now 2.9.0) for the versioned download URL.

## Upgrade notes
Existing v2.8 instances keep their already-seeded barcode mappings and
products (config/data are untouched). To start from a clean barcode
list, delete the mappings in the Barcodes tab's edit mode; to (re-)add
the Sweden list, use Settings → Barcodes.

Web app version: 2.9.0.
