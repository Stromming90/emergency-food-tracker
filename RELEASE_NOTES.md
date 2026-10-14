# v2.7.1 — Android app hotfix

- **SSO now stays in the app:** logging in with Keycloak (or any OIDC
  provider) previously jumped out to the browser and left you logged in
  there instead of the app. All http/https navigation — including the
  identity provider — now stays inside the app's WebView, so the session
  cookie belongs to the app and you return to it after authenticating.
- **Setup screen readability:** the first-launch screen (where you enter
  the server address) had dark text on a dark background; text and hint
  colours are now light and clearly readable.

App version 2.7.1 (versionCode 28). Signed with the same key as 2.7, so it
installs directly over the existing app.
