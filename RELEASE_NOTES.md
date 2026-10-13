# Release v2.4.1

Bugfix release for v2.4.

## Fixed

- **Blank page after login.** A missing `id` on the "Create user" button caused a
  script error at page load, which stopped the entire app from rendering. The
  page now loads normally again.
- **Product list migration.** On startup, v2.4 could move the shared product list
  into a household folder and leave an empty global list behind, losing all your
  products. Migration now merges every existing product source (old flat
  `products.csv` and per-household copies) into the global list, deduplicating
  on name + manufacturer. Your products survive the v2.4 upgrade.
- The "All" chip in the Household inventory now renders with a capital "A".
