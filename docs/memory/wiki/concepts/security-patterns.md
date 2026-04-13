# Security Patterns

> Secrets in environment variables, XSS escaping on all scraped data, TLS verification always enabled, and safety thresholds for bulk operations.

**Applies to:** [Zillow Scraper](../entities/zillow-scraper.md), [Realtor Scraper](../entities/realtor-scraper.md), [Notification System](../entities/notification-system.md), [Config (YAML)](../entities/config-yaml.md), [Listing Card](../entities/listing-card.md), [Map View](../entities/map-view.md)  
**Learned:** 2026-03-27  
**Source:** `docs/memory/shared/systemPatterns.md` — Security Patterns + `docs/memory/shared/lessonsLearned.md` — Code Review Patterns

## Pattern

Security in SunnyNest follows defense-in-depth across four areas: secrets management, XSS prevention, TLS verification, and bulk operation safety.

## Rules

### Secrets Management
1. **API keys and passwords in environment variables** — `RAPIDAPI_KEY`, `SMTP_PASSWORD`, `NOTIFICATION_RECIPIENT`, `ADMIN_SECRET_KEY`
2. **Never put real secrets in `config.yaml`** — empty defaults only, with env var override
3. **`.env` file is the single source of truth** — `load_dotenv()` reads it at startup
4. **`.env.example` documents all required env vars** — update when adding new dependencies

### XSS Prevention
5. **HTML-escape all scraped data** before rendering — listing titles, URLs, addresses, image URLs
6. **Don't forget map popups** — Leaflet popup HTML is just as vulnerable as card HTML
7. **Use `html.escape()`** on all user-visible scraped content in both templates and JavaScript

### TLS Verification
8. **All HTTP clients use custom SSL context** via `BaseScraper._build_ssl_context()` — loads certifi CA bundle + PANW Enterprise Root CA for TLS decryption proxy compatibility
9. **Never use `verify=False`** — the original Zillow scraper had this and it was a P1 fix
10. **OpenSSL 3.6+ compatibility** — `VERIFY_X509_STRICT` flag is cleared to handle Palo Alto proxy leaf certs missing the Authority Key Identifier (AKI) extension. All other security properties preserved: `CERT_REQUIRED`, `check_hostname=True`, full chain validation
11. **PANW root CA stored at `data/certs/panw-root-ca.pem`** — graceful degradation if file absent (falls back to certifi-only)

### Bulk Operation Safety
10. **`mark_inactive()` requires seeing ≥30% of active listings** before deactivating unseen ones
11. **Prevents data loss from partial scrape failures** — if a scraper returns only 5 of 30 listings, don't deactivate the other 25

## Examples

- **API key in config (2026-03-27):** `RAPIDAPI_KEY` was stored in `config.yaml` — moved to env var
- **TLS disabled (2026-03-27):** Zillow scraper had `verify=False` — restored to default
- **PANW TLS proxy (2026-04-06):** Palo Alto Networks GlobalProtect firewall performing TLS decryption caused SSL failures. Fixed with custom SSL context loading PANW root CA + clearing `VERIFY_X509_STRICT` for OpenSSL 3.6 AKI compatibility
- **XSS in map popups (2026-03-27):** Map popup HTML rendered unescaped listing data — fixed with `html.escape()`
- **Mass deactivation risk:** Without the 30% threshold, a Zillow API outage could deactivate all listings

## Related

- [Environment Validation](environment-validation.md) — startup checks for env vars
- [Silent Failure Pattern](silent-failure-pattern.md) — what happens when credentials are missing
- [Config (YAML)](../entities/config-yaml.md) — empty defaults for secrets
