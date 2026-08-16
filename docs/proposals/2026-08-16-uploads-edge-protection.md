# Protecting the image read path from scrapers

**Status:** proposed — nothing here is implemented | **Date:** 2026-08-16

The read path itself shipped in #202: the Storm bucket is private, and
[`workers/uploads-proxy`](../../workers/uploads-proxy/) is the only reader, a
Cloudflare Worker holding a Read Only per-bucket key that signs each GET and
caches at the edge. It is live on `img-dev.cha.fan`.

This plan is about what that design does *not* cover. Nothing here is urgent
today; it is written down because the trigger for needing it is external and
sudden, and by then is a bad time to be working out what the options were.

## The problem

There are two budgets, and the Worker only defends one of them.

**Storm egress** is defended well. Objects are content-addressed and served
`immutable`, so a real reader fetches each image once, ever; and repeats from
other readers are answered by `caches.default` inside the Worker, which puts
Storm at roughly one fetch per object per Cloudflare PoP.

**Worker invocations are not defended at all.** The Worker runs on *every*
request, hit or miss, because a Worker on a Custom Domain is the origin — the
cache lookup happens inside it, not in front of it. Measured on the live
hostname: a URL Cloudflare had never seen before (`?v=<random>` appended to a
cached object) still returned `cf-cache-status: HIT` with the same `age` as the
plain URL, which can only happen if the Worker executed and did its own
normalized cache lookup. Zone caching keys on the full URL including the query,
so a cache-in-front would have missed.

So the shape of the exposure is:

| Traffic | Storm egress | Worker invocations |
| --- | --- | --- |
| Same images fetched repeatedly | flat | climbs |
| Distinct real keys walked | climbs | climbs |
| Well-formed keys for absent objects | negligible (404s are small) | climbs, and reaches Storm every time — 404s are not cached |

On the Workers **free** plan the ceiling is 100k requests/day, and crossing it
returns Cloudflare error **1027** for the rest of the UTC day. That is a cliff,
not a slope: every image on the site breaks at once, and recovers on a clock
rather than on an action. Chafan 1.0 was taken down by scraper load, which is
the reason this document exists rather than being a theoretical exercise.

## What makes the fixes cheap

Cloudflare's request pipeline runs WAF custom rules, rate limiting and bot rules
*before* Workers. A request blocked there never invokes the Worker and never
counts against the quota. So the defenses cost nothing to run, and the ones that
matter most are dashboard configuration rather than code.

That is also their weakness as a plan: none of it lives in this repo, so nothing
in a branch or a review will tell you that a rule is missing or was turned off.
Hence the config being written down here.

## Measures, in the order worth doing them

### 1. Rate limiting rule on the hostname

Free, and the highest value item. Match `http.host eq "img-dev.cha.fan"`,
characteristic **IP**, action Block. The threshold has to clear a legitimate
page load — a single answer can pull a dozen images at once — so something
around 100 requests / 10 seconds rather than anything tight.

Does not help against a distributed crawler; does stop the single-IP hammering
that is most of the volume.

### 2. Bot toggles

Security → Bots: **Block AI Scrapers and Crawlers**, and Bot Fight Mode. Both act
ahead of Workers. The AI-crawler switch is the closest thing to a direct answer
to what happened to 1.0.

Bot Fight Mode on the free tier is blunt and will occasionally challenge real
users. Worth a day of watching after enabling, and worth turning back off if it
costs more than it saves.

### 3. Referer rule

Images are only ever loaded from answer pages on `cha.fan` / `dev.cha.fan`. A
free WAF custom rule blocking requests whose `http.referer` is neither empty nor
a cha.fan host removes naive scrapers for one rule slot.

The empty case must be allowed: browsers strip referer in privacy modes, and
"open image in new tab" sends none. This is a filter for the lazy, not a
boundary — referer is trivially forged.

### 4. Workers Paid

$5/month for 10M requests included, with overage billed rather than refused.
Every other item on this list reduces the odds of hitting the ceiling; this one
changes what happens when something eventually does. For a project whose
predecessor died of exactly this, it is the cheapest insurance in the stack, and
the recommendation is to take it before the other items rather than after.

The last two are the only items that are code, and both are in
[`src/index.ts`](../../workers/uploads-proxy/src/index.ts).

### 5. `robots.txt` from the Worker

`/robots.txt` currently 404s, because it does not match `KEY_PATTERN` and every
non-matching path is rejected. A crawler that finds an image URL checks
robots.txt *on the image's own host*, so `img-dev.cha.fan` needs to serve its
own — the one at `dev.cha.fan` says nothing about it.

Handle it ahead of the key check, before anything is signed:

```ts
if (url.pathname === '/robots.txt') {
  return new Response('User-agent: *\nDisallow: /\n', {
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'public, max-age=86400',
    },
  });
}
```

`Disallow: /` is right for this host specifically: nothing here is a page, and
nothing here benefits from being indexed. The images are reachable from the
answer pages, which is where indexing belongs.

This is voluntary compliance and stops nobody hostile. It is on the list because
polite crawlers are most of the *baseline* volume, and removing them costs one
`if`. Serving it does cost an invocation per fetch, but crawlers request
robots.txt on the order of once a day, not once an image.

Do the same on `img.cha.fan` when prod goes up — it is the same code path, so
this is automatic as long as prod deploys from the same source.

### 6. Cache negative responses

The Worker only calls `cache.put` on success, so a well-formed sha for an object
that does not exist reaches Storm on *every* request. It is the one path with no
protection at all: `KEY_PATTERN` lets it through (it is well-formed by
construction), the signing happens, the upstream fetch happens, and the 404 that
comes back is thrown away rather than remembered.

The Cache API honors the `Cache-Control` on whatever response you put, so a
short TTL on the negative case is enough:

```ts
if (!upstream.ok) {
  const status = upstream.status === 404 ? 404 : 502;
  const miss = new Response('Not found', {
    status,
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'public, max-age=60',
    },
  });
  if (status === 404) {
    ctx.waitUntil(cache.put(cacheKey, miss.clone()));
  }
  return miss;
}
```

Only 404 is worth caching. A 502 means Storm was unreachable or the key was
rotated out from under us, and caching that would extend an outage past its own
end.

The cost of getting the TTL wrong is a not-yet-existing object staying invisible
for up to 60 seconds after it appears. In practice that window is unreachable:
the URL is derived from the sha and only handed to the client after
`put_object` returns, so nothing knows the URL before the bytes are there. Keep
the TTL short anyway — the value here is bounding a flood, and a flood is
bounded just as well at 60 seconds as at an hour.

## The fork this deliberately does not take

The structural way to make cache hits cost nothing is an origin Cloudflare can
cache natively, with no Worker in the path — Storm Static Hosting behind a
proxied CNAME would do it, and invocations would stop being a budget at all.

That was considered and rejected when the read path was designed, because
enabling Static Hosting publishes a `stormsites.ca` URL that cannot be turned
off while serving. A scraper that learns that hostname bypasses Cloudflare
entirely: no cache, no rate limit, and Storm egress billed directly. Trading a
raisable invocation ceiling for an uncapped egress bypass is the wrong
direction.

Revisit only if invocation count becomes a real constraint rather than a
theoretical one, and even then prefer paying for invocations first.

## How we would find out

There is no alerting on any of this. The signals, in the order they would
appear:

- Workers analytics in the Cloudflare dashboard: requests/day approaching 100k.
- Reports of broken images site-wide that fix themselves overnight — that is
  error 1027 and nothing else.
- Storm's own egress figure moving without a matching rise in real usage, which
  would mean the edge cache is being bypassed rather than the Worker overrun.

## Open

- Nobody has confirmed which of the free-tier bot features are actually
  available on this account; the dashboard is the authority, not this file.
- The prod hostname (`img.cha.fan`) needs the same rules as `img-dev.cha.fan`
  when it goes up, and there is currently nothing that would notice if it did
  not get them.
