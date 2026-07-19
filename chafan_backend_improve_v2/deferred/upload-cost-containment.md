# Deferred: Upload Cost Containment

**Status:** Deferred from `../proposals/15-image-upload-r2.md`. Revisit after R2 is live and stable.

## What this proposal would do

Harden the image-upload endpoint against abuse (scraper floods, single-user runaway, buggy client retries) and give ops visibility into upload health.

Five cost-containment layers (from the original `image_upload_plan.md`):

1. **slowapi rate limit** on the upload routes specifically — distinct from the default `150/minute` so upload can be tighter.
2. **Redis-backed per-user counter** — limits a single logged-in user to N uploads per hour/day even across multiple IPs.
3. **Global killswitch** — `UPLOAD_KILLSWITCH: bool = False`. When true, all uploads get a 503 with a clean client-facing message. Flag is flipped via config, no deploy required if wired to `settings`.
4. **Cloudflare WAF rules** — block known scraper patterns, optionally challenge anonymous traffic.
5. **Cloudflare cost alerts** — ops-side dashboard / alerting on R2 egress / operations costs.

Plus:

- **Hourly canary job.** APScheduler task uploads a tiny known image, verifies round-trip, alerts on failure. Registers into the APScheduler instance that `../proposals/04-scheduled-consolidation.md` makes canonical.
- **`chafan_auth=1` presence cookie** so CF edge can distinguish authenticated users from anonymous scrapers for caching/WAF decisions. Cookie set on login, cleared on logout. No sensitive data in the cookie.
- **Optional coin deduction per upload.** `UPLOAD_COIN_COST: int = 0` (disabled by default). If enabled, routes through `rep_manager.deduct_coins(user, UPLOAD_COIN_COST, "image_upload")`. Contract defined by `../proposals/08-rep-manager-centralization.md`; all that's needed here is the call site.

## Why it's deferred

1. **The rate-limiting design needs future work.** Per-user-counter semantics, interaction with slowapi's IP-based limits, dev-environment bypass rules — these are not trivial and the current plan sketch doesn't cover the edge cases. Needs a dedicated design pass.
2. **Keeping these out of `15` keeps the R2 migration shippable.** The R2 swap is mechanical and low-risk on its own. Bundling it with a 5-layer abuse story inflates review burden and risk.
3. **Server load is low and self-hosted** (see project memory). No current billing pressure or abuse signal forces this. It's prudence, not urgency.

## What would trigger revisiting

- First sustained abuse episode (scraper flood, single user chewing through quota, CF cost alert firing).
- Any public linking of upload URLs that draws anonymous traffic.
- A product decision to enable the per-upload coin hook (turning uploads into a "costs the user something" action rather than a free affordance).
- R2 migration has been live for 60+ days with no issues and we're ready to layer on complexity.

## Dependencies if revisited

- `../proposals/04-scheduled-consolidation.md` — canary job slot.
- `../proposals/08-rep-manager-centralization.md` — coin hook routing.
- `../proposals/10-request-logging.md` — logger name convention (`chafan.upload` for upload events, `chafan.upload.canary` for canary results).
- `../proposals/15-image-upload-r2.md` — the endpoint the rate limits wrap.

## What NOT to do when revisiting

- Don't re-bundle all five layers into one PR. Ship them individually: killswitch first (cheapest, highest-value), then slowapi route-specific limits, then per-user counter, then canary, then CF-side rules.
- Don't add `is_dev()` bypasses. If dev needs looser limits, put it behind a config flag that happens to default to "loose" in dev env files — same mechanism prod uses, just tuned.
- Don't wire the coin hook "just in case." It stays at `UPLOAD_COIN_COST=0` until there's a product reason to turn it on.
