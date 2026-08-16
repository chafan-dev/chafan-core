# uploads-proxy

The public read path for image uploads. The backend writes objects to a private
Storm bucket; this Worker is the only thing that can read them back.

It lives in this repo rather than the PWA repo because it is the read half of
the upload feature whose write half is `chafan_core/app/object_storage.py` — the
`<sha256>.<ext>` key format is defined there and duplicated here as
`KEY_PATTERN`, and the two must not drift. It is also deployed independently of
the frontend's `master → deploy/preview → deploy/master` promotion chain.

## Why a Worker rather than a public bucket

Garage serves no anonymous S3 request and implements no bucket policy, so
"just make the objects readable" is not available. Storm's alternative is
Static Hosting, which is a per-bucket switch that exposes the whole bucket at a
`stormsites.ca` URL. That URL cannot be turned off while serving, so putting
Cloudflare in front of a custom domain would not help: a scraper that learns the
`stormsites.ca` hostname bypasses the cache and the rate limits and bills the
egress to us anyway.

Keeping the bucket private and signing per request closes that. Repeat traffic
is answered from Cloudflare's edge cache, so Storm sees roughly one fetch per
object per PoP; rate limiting and hotlink rules apply because the hostname is an
ordinary zone entry; and no bytes cross the chafan server or its tunnel.

## What the edge does and does not do for you

Being on a Cloudflare custom domain is not what makes this cached. A Worker on a
custom domain *is* the origin: it runs on every request, and no zone cache sits
in front of it. The caching is the `caches.default` calls in `src/index.ts` and
nothing else — remove them and every view becomes a Storm fetch, with no error
and no change in behavior anyone would notice until the egress bill.

Three consequences worth holding onto:

- **The cache is per-PoP.** A reader in a city that has not seen an object yet
  pays one Storm fetch for it. Live on `img-dev.cha.fan`, a cold request returns
  no `cf-cache-status` header at all; the next one reports `HIT` with an `age`.
- **Invocations are billed on hits**, since the Worker runs before the cache.
  Free tier is 100k/day, which is far above anything this serves.
- **404s are not cached.** A well-formed key for an object that does not exist
  reaches Storm on every request. The body is tiny, so this is a request-rate
  cost rather than an egress one, and the zone rate-limit rule below is what
  bounds it.

## Deploy

1. **Mint a Read Only key.** In the Storm dashboard, open the bucket's keys and
   generate the **Read Only** per-bucket key (the tier documented as "for CDNs
   and integrations": list and download, nothing else). The secret is shown
   once. Do not reuse the Read / Write key the backend uses — this one lives in
   Cloudflare and only needs to read.

2. **Do not enable Static Hosting.** The bucket must stay private for any of the
   above to hold.

3. **Publish, then set the secrets on the Worker that deploy just created:**

   ```bash
   cd workers/uploads-proxy
   npm install
   npx wrangler deploy --env dev
   npx wrangler secret put UPLOADS_S3_ACCESS_KEY_ID --env dev
   npx wrangler secret put UPLOADS_S3_SECRET_ACCESS_KEY --env dev
   ```

   Each `secret put` gives you a hidden `Enter a secret value:` prompt — paste,
   enter. Nothing touches your shell history or the disk, and wrangler never
   reads a same-named variable out of your environment, which matters here
   because `launch_env` exports `UPLOADS_S3_ACCESS_KEY_ID` as the *Read / Write*
   key.

   Deploy comes first because `secret put` against a Worker that does not exist
   yet offers to create a bare one, without these vars or the route. The gap is
   harmless: nothing points at the hostname until step 4, and the Worker just
   502s. Secrets apply immediately, so no second deploy.

   The endpoint, bucket and region are plain `vars` in `wrangler.toml`; only the
   key pair is a secret. `npx wrangler secret list --env dev` confirms both
   landed — names only, values are write-once.

4. **Point the backend at it** and restart the server:

   ```
   UPLOADS_PUBLIC_URL_BASE=https://img-dev.cha.fan
   ```

5. **Verify** from the repo root, which fetches every object in the bucket
   anonymously through the Worker and compares each against a signed
   `head_object`:

   ```bash
   python scripts/check_upload_public_read.py
   ```

## Rate limiting

Not in this Worker — it belongs in the zone, where it runs before the request
costs anything. In the Cloudflare dashboard, under Security → WAF → Rate
limiting rules, for `img-dev.cha.fan`:

- Match `http.host eq "img-dev.cha.fan"`, characteristic **IP**, and pick a
  threshold well above a page's worth of images (a single answer can legitimately
  pull a dozen at once) — say 100 requests per 10 seconds, action Block.

Cache hits are served before the origin fetch, so this caps a scraper's request
rate; the edge cache is what actually caps Storm egress.

## Local development

`wrangler dev` reads secrets from `.dev.vars` (gitignored):

```
UPLOADS_S3_ACCESS_KEY_ID=GK...
UPLOADS_S3_SECRET_ACCESS_KEY=...
```

Note that `caches.default` is a no-op locally, so `wrangler dev` exercises the
signing and the response shape but never the caching.

To check the signature alone against the real bucket, without a Workers runtime:

```bash
UPLOADS_S3_ENDPOINT_URL=https://alpha.buckets.stormdevelopments.ca \
UPLOADS_S3_BUCKET=chafandev2026 UPLOADS_S3_REGION=storm \
UPLOADS_S3_ACCESS_KEY_ID=... UPLOADS_S3_SECRET_ACCESS_KEY=... \
node --experimental-strip-types scripts/sign_check.ts <sha>.jpg
```

A missigned request and an unsigned one both come back as the same Garage 403,
which is exactly why that check exists.
