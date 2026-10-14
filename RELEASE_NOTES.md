# v2.6 — SSO display name, tidier settings

## Authentication (Settings → Authentication)
- New **Display name** field in the OIDC configuration. The name is shown on the
  sign-in page's SSO button, e.g. `Keycloak` → **Login with Keycloak** (falls
  back to "Login with SSO" if no name is set).
- The SSO options are now one checkbox per row, label first and box on the
  right, with proper capitalization:
  - Auto-create unknown users on first SSO login
  - Enable SSO login (show the single sign-on button)
  - Disable username/password login
- Renamed "Save OIDC settings" → "Save authentication settings".

## Settings layout
- Users, Households and Authentication tabs tidied up: tighter spacing between
  sections, aligned rows and consistent capitalization ("Global admin",
  "Households for the new user", etc.).
