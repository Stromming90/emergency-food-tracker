## v2.3

Products setup overhaul, based on curated emergency-food categories — plus easier inventory management.

### Products tab (overhauled)

- New **"Set up your product list"** card: pick one of nine curated emergency-food categories (dry staples & carbohydrates, canned & jarred ready foods, protein, fats & cooking, extras & sweeteners, beverages, instant meals, snacks & morale, supplements), see its typical **storage** and **shelf-life range**, then click suggested items to add them to the global product list in one click. Already-added items are marked with a ✓.
- The manual add form and the admin edit dialog now use a category dropdown instead of free text.
- The product list shows category labels (legacy free-text categories are still displayed and selectable).

### Household tab

- **Record a purchase:** the product dropdown can be filtered by category (new dropdown next to it). When the best-before field is empty, selecting a product pre-fills a suggested date from its category's typical shelf life.
- **Inventory:** the quantity of an existing item can now be changed directly in the table (inline number field next to each row). To remove an item entirely, use the ✕ button as before.

Upgrade as usual: `docker compose pull && docker compose up -d`. No data migration — existing products and inventory are untouched (legacy free-text categories keep working).
