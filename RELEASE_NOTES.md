# Release v2.4.2

Bugfix release for v2.4 / v2.4.1.

## Fixed

- **SSO behind bot-protection (Cloudflare etc.).** The server's outbound OIDC
  requests (discovery, token exchange, userinfo) used Python's default
  `Python-urllib` User-Agent, which bot-protection layers such as Cloudflare
  Bot Fight Mode block with a 403 — breaking SSO login with an
  "OIDC discovery failed … HTTP Error 403" error. All outbound OIDC requests
  now send a browser-like User-Agent, so SSO works without any changes to
  your reverse proxy or Cloudflare configuration.
