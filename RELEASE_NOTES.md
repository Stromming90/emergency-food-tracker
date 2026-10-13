## v2.4

Finer-grained permissions, personal API keys, and a more deliberate inventory UI.

### Roles & Settings

- **Two admin roles:** **global admin** (access to do and see everything) and **household admin** (edit the product list, migrate inventory between households, manage the users of their households, and grant/revoke household-admin rights for those households).
- Settings menu opens on a new **General** tab with an explanation of what can be done where. Tabs: General · Users · Households · Authentication (global admin) · API Key.
- **Personal API keys:** every user now has their own unique API key, viewable and regenerable in Settings → API Key. The widget only reports households the key's owner has access to.
- **Households:** any user can create a household and becomes its household admin; the implicit "default" household is gone — the first user names their first household at setup. User lists in the Households tab are one per line; household lists in the Users tab are one per line.

### Household tab

- *Record a purchase:* the Type dropdown shows the number of available products for each type.
- *Inventory:* quantity editing is now behind a deliberate ✎ button (no more accidental changes), the status filter dropdown is gone — instead the colour-coded badges (All · Fine · Less than 6 months · Less than 3 months · Less than 1 month · Expired) are clickable filters, all capitalised.

### Products tab

- v2.3's "categories" are now **types**; the sub-categories (ravioli, stew, pasta, …) are the **category** suggestions per type. "Snacks & morale" is now just **Snacks**.
- Adding a product now takes **type, category, product name, manufacturer and size** (grams/millilitres). The product table shows Type, Category and Size, all sortable and filterable.

Upgrade as usual: `docker compose pull && docker compose up -d`. On first start, existing users are migrated to the new role model and get personal API keys; old product categories are converted to types automatically. Previously configured widget API keys are replaced by the personal keys — get yours from Settings → API Key.
