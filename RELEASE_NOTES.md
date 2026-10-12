# Release v2.2 — Widget counts real stock, Products tab & inventory filtering

## 📊 Homepage widget

- **`total_items` now reports the total quantity of items in stock** — the sum of
  all quantities (the actual number of cans/units), instead of the number of
  inventory entries. `total_quantity` remains an alias with the same value.
- New **`total_entries`** field for the number of distinct inventory rows.
- The per-household breakdown now includes both `total_items` (quantities)
  and `total_entries`.

## 📋 Products tab

- The global product list moved to its own **Products** tab, separate from the
  household view.
- Admins edit products in a proper dialog where **all fields** (name,
  manufacturer, category) are editable — changes propagate to every
  household's inventory.
- Filter products by text (name / manufacturer / category) and sort by
  clicking any column header.

## 🏠 Household tab

- **Record a purchase** now sits at the top of the page, with the inventory
  below it.
- Inventory can be **filtered** by free text (product / manufacturer) and by
  expiry status: Fine · Less than 6 months · Less than 3 months ·
  Less than 1 month · Expired.
- **Sortable columns** — click Product, Qty, Best before, Days or Status to
  sort ascending/descending; the Status column sorts by urgency, not
  alphabetically.
- The header line shows both total units in stock and the number of entries.

## 🏷️ Misc

- The household selector in the top bar is now labelled **"Household:"**.
- The Docker image is now also tagged with the release version
  (e.g. `ghcr.io/stromming90/emergency-food-tracker:v2.2`) alongside `latest`.
- Releases are now created automatically by GitHub Actions whenever the
  `VERSION` file changes.

## 🔄 Upgrading

```bash
docker compose pull && docker compose up -d
```

No data migration needed — v2.1 data layouts are unchanged.
