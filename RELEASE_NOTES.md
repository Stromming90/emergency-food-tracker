# v2.10.0 — Types & Categories tab, notifications, safer edit modes

## Mobile app
The downloadable APK is always named after the current version — with
this update it is served as **emergency-food-tracker-2.10.0.apk** —
even though the app binary itself is unchanged. The app is a thin
WebView wrapper: every feature below arrives through the web UI the
moment the server is updated, so **no reinstall is needed**.

## Household
- **Inventory**: the big filter box is gone — the per-column filters
  stay and cover everything it did (the Product column filter also
  matches the manufacturer).

## Products
- The product list's big filter box is gone — per-column filters only.
- **Removing products is locked behind an edit button**: the ✕ remove
  buttons only appear after pressing **✏️ Edit** (press **Done** to
  exit). Editing a product's details still uses the ✎ button.

## Barcodes
- Behind the **✏️ Edit** button, global admins can now also **change
  existing mappings**: each row gets a ✎ that opens it for inline
  editing — change the barcode, pick a different product (brand and
  size follow automatically) — then buffer the changes and press
  **Confirm changes**. Removals and new mappings work as before, all
  buffered until you confirm.

## Types & Categories (moved out of Settings)
- The Types tab moved from Settings to **a tab on the main page** and
  is renamed **Types & Categories**.
- Access is **global admin only**.
- The tab shows a read-only table (type, categories, shelf life in
  months); editing is locked behind an **✏️ Edit** button with
  Save / Cancel, and **+ Add type** / **Reset to defaults** only
  appear while editing.

## Settings → Notifications (new)
- A new **Notifications** section with a toggle for push notifications
  on this device (plus a test button).
- The app now **alerts you when items change status tag** — "Less than
  6 months", "Less than 3 months", "Less than 1 month" or "Expired" —
  e.g. when a best-before date crosses a threshold. Checks run whenever
  the app refreshes (about once a minute while open, and after every
  change). Uses the browser/WebView notification system; grant
  permission when prompted.

Web app version: 2.10.0.
