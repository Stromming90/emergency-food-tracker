# v2.5 — SSO controls, editable types, inventory edit mode, Information tab

## Authentication (Settings → Authentication)
- New option to enable/disable the OIDC/SSO login button.
- New option to disable username/password login (only selectable while SSO is configured and enabled, so you can never lock yourself out). When disabled, the login form is hidden and only the single sign-on button is shown.

## Settings → Users
- Users are listed first (name, role, assigned households), with the create-user section below.
- Edit-user dialog now shows one clear list: a "global admin" checkbox plus every household with a **member** and a **household admin** checkbox each.

## Settings → Households
- New **Edit household** section: change which users are assigned to an existing household at any time.
- Delete and Migrate dropdowns now default to unselected, and both actions ask for confirmation ("Are you sure you want to remove/migrate this household?") before running.

## Household → Inventory
- New **Type**, **Category** and **Size** columns (sortable).
- The Inventory section is now locked behind an **Edit inventory** button; changes (add/remove quantity, edit quantity, delete rows) are buffered and applied with **Save**, or discarded with **Cancel**.
- Next to the ✎ edit button there are now ➕/➖ buttons for quick quantity changes.

## Products
- The category field is now a dropdown fed by the selected type.
- New **Types** settings tab (global admin): add, rename and remove product types and category options, or reset everything to the defaults.
- Category/label changes: added *sauce* (Canned & jarred foods), *water* (Beverages) and *mashed potato powder* (Dry staples & carbohydrates); *cocoa* renamed to *chocolate powder*; *Canned & jarred ready foods* renamed to **Canned & jarred foods**; canned fish moved from Canned & jarred foods to **Protein**.

## New Information tab
- Added a preparedness guide (one-week/two-week food & water targets, what to stock, how to rotate it) with links to official sources: Livsmedelsverket, Ready.gov, CDC, Gov.uk, Pretatenir.fr and BBK.

## Fixes
- Fixed character corruption (mojibake) introduced in v2.4.1 — non-ASCII characters (é, å, ä, ö, —, emoji) in the UI and server are correct again.
- Fixed the product list migration so upgrading from v2.3 keeps the global product list.
- API requests no longer send a `Python-urllib` user agent (fixes 403 errors behind Cloudflare Bot Fight Mode for OIDC discovery and removes the need for a Cloudflare user-agent exception rule).
- Fixed a regression where an API call without a household parameter could silently re-create a `default` household directory.
