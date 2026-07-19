# 15: Image Upload — Cloudflare R2 Rewrite + Dev/Prod Unification

**Phase:** 4 — Image upload rewrite | **Effort:** 3-5 days | **Risk:** Medium

**Scope reduction note:** The original draft bundled R2 migration with a 5-layer rate-limiting stack, a killswitch, and an hourly canary. Those pieces are **moved to `../deferred/upload-cost-containment.md`** — the rate-limiting design needs future work and gating the R2 rewrite on it was over-scoped. This proposal is now: swap S3 for R2, delete the picsum dev short-circuit, get it working in prod again.

**Source plan (partial reference):** `/var/home/lizhenbo/src/chafan/image_upload_plan.md` (~450 lines — keep as infra checklist for R2 bucket + CF edge config; ignore the cost-containment sections).

**Depends on:**
- `06-dev-prod-unification.md` — removing the upload-endpoint `is_dev()` branch is a concrete example of that proposal's principle (now consolidated here; A6 is superseded).
- `08-rep-manager-centralization.md` — the optional coin hook, if ever enabled, routes through `rep_manager.deduct_coins(user, 1, "image_upload")`.
- `10-request-logging.md` — logger name convention.

---

## Status quo

Current state of `chafan_core/app/api/api_v1/endpoints/upload.py`:

- Two endpoints: `POST /upload/images/` (single file) and `POST /upload/vditor/` (multi-file, for the editor).
- **Dev path is a picsum stub** (`is_dev()` branches at lines 25-26 and 63-72) — returns `https://picsum.photos/200/300`. This is a dev/prod divergence that must go per `06-dev-prod-unification.md`.
- **Prod path is S3 + CloudFront** via `chafan_core/app/aws.py:get_s3_client`. Content-addressed (SHA-256 hex of bytes → object key). User confirms this is **broken in production**: don't assume the existing prod flow works end-to-end as-is. Some of the code logic (the SHA-256 streaming, the NamedTemporaryFile pattern, the `ExtraArgs` cache header) is reusable; be prepared to rewrite.
- Depends on `settings.S3_UPLOADS_BUCKET_NAME`, `settings.AWS_CLOUDFRONT_HOST`, and whatever the `get_s3_client` helper reads.

## Goal

1. Replace S3 + CloudFront with Cloudflare R2 + public R2 domain (or CF-cached subdomain).
2. Delete both `is_dev()` branches — dev uses the same code path, pointed at either a dev R2 bucket or a local MinIO instance via configurable endpoint URL.
3. Get upload working in prod again.

Anything beyond those three goals is out of scope for this proposal. Cost containment (rate limits, killswitch, canary) is a separate problem parked in `../deferred/upload-cost-containment.md`.

## Design

- boto3 client talking to R2 (R2 is S3-compatible; configure `endpoint_url` + account credentials). Much of the existing `upload.py` body survives — what changes is the client construction and the URL-building logic.
- Content-addressed storage stays: SHA-256 hex → object key. Same content → same key → no duplicate storage. No per-upload randomness.
- Public bucket served via `uploads.cha.fan` (or whatever domain is configured).
- **Salvage what's still good from the S3 code:** the streaming read into `NamedTemporaryFile`, the SHA-256 hashing pattern, the `Cache-Control` header. Rewrite the client wiring, the URL output, and any bits that are actually broken in prod.
- Delete `aws.py` only if no other code still depends on it; otherwise leave it alone — this proposal is not an AWS purge.

## Picsum deletion

- Delete both `is_dev()` branches in `upload.py`.
- Delete any frontend test fixtures that assert the picsum URL (if any).
- In dev, either (a) point at a dev R2 bucket (cheap, simplest) or (b) run a local MinIO container and point boto3 at `http://localhost:9000`. Make the endpoint URL configurable so both work.

## Config surface

Minimal set needed to ship (finalize against `image_upload_plan.md`'s operational checklist):

- `R2_ENDPOINT_URL` — e.g. `https://<account_id>.r2.cloudflarestorage.com`; or a MinIO URL in dev if preferred
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID` (secret)
- `R2_SECRET_ACCESS_KEY` (secret)
- `UPLOAD_PUBLIC_DOMAIN` — default `uploads.cha.fan`
- `UPLOAD_MAX_BYTES` — size cap (pick from `image_upload_plan.md`)

No `is_dev()` branches anywhere in the upload path.

Not added here (parked in `../deferred/upload-cost-containment.md`):
- `UPLOAD_KILLSWITCH`
- `UPLOAD_COIN_COST`
- `UPLOAD_CANARY_ENABLED`
- Per-user rate-limit counters, slowapi rules specific to upload, CF WAF rules, CF cost alerts

## Rollout

1. Stand up an R2 bucket + domain per the `image_upload_plan.md` operational checklist (bucket policy, CORS if needed, public access, CF caching rules).
2. Add R2 settings to config.
3. Replace the boto3 client construction in `upload.py` (or a new helper) to target R2 via `endpoint_url`.
4. Delete the `is_dev()` branches.
5. Test uploads end-to-end in staging / dev against the dev bucket (or MinIO).
6. Deploy. Verify with a manual upload from the PWA.
7. If the old S3 bucket still holds any useful objects, leave it for now — decommissioning the old stack is a follow-up, not a blocker.

## Acceptance

- `POST /upload/images/` and `POST /upload/vditor/` work identically in dev and prod.
- Zero `is_dev()` in `upload.py`.
- Uploaded files land in R2, served via the configured public domain.
- Content-addressed keys preserved (same bytes → same URL).
- Frontend uses the URLs without changes (response shape unchanged).
- `aws.py` either removed or clearly unused by the upload flow.

## Out of scope (moved to `../deferred/upload-cost-containment.md`)

- 5-layer rate limiting (slowapi, Redis counter, killswitch config, CF WAF, CF alerts)
- Hourly upload canary via APScheduler
- `chafan_auth=1` presence cookie for CF edge decisions
- Optional per-upload coin deduction

These are valuable but they are a separate cost/ops project. Shipping the R2 migration should not wait for them.

## Related

- Supersedes v1 Proposal 07 A6 entirely. That sub-item is dropped from `06-dev-prod-unification.md`.
- The picsum mock in `chafan_core/app/api/api_v1/endpoints/upload.py` (lines 25-26, 63-72) goes away as part of this work.
