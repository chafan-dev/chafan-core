# Proposal: Resilience against aggressive (hostile) crawler load

- **Date:** 2026-05-29
- **Status:** Draft for review
- **Scope:** `chafan-core` backend (`api.cha.fan`)
- **Trigger:** A post-deploy smoke run hit a `500` whose server log mentioned a *timeout*. Investigation suggests aggressive bot/crawler traffic can drive the origin into the same timeout condition.

---

## 1. Threat model (the assumption everything else follows from)

We assume crawlers are **hostile and uncooperative**:

- They ignore `robots.txt`, `Crawl-delay`, and any voluntary hint.
- They spoof or omit `User-Agent`, so UA allow/deny lists are weak.
- They may crawl from **many rotating IPs**, so per-IP identification degrades.

Consequence: **we do not try to identify or out-argue the bot.** We make the
server *stay up and stay fair* under arbitrary aggregate load. The strategy is
**resource isolation + enforced limits**, never cooperation.

Explicitly **rejected** as load-bearing defenses:
- `robots.txt` / crawl-delay hints (voluntary).
- `User-Agent`-based blocking as the primary control (spoofable).

These may exist as cheap extras, but nothing critical depends on them.

---

## 2. How the system actually handles a request (root cause)

Findings from the current code and deploy scripts:

| Fact | Source | Implication |
|---|---|---|
| **216 sync `def` endpoints, 1 async** | `chafan_core/app/api/api_v1/endpoints/*.py` | Every REST request runs in Starlette's anyio **threadpool**, not the event loop. |
| **No threadpool tuning** | `chafan_core/app/main.py` (no `total_tokens` / limiter override) | Concurrency is capped at anyio's default **~40 threads**. The 41st concurrent request **queues**. |
| **Single uvicorn process** | `scripts/launch_serv/_fastapi.sh` (no `--workers`, no gunicorn) | The 40-thread cap is the whole app's concurrency budget. |
| **DB pool = 60 + 20 overflow = 80/process** | `chafan_core/db/session.py`, `config.py:18-19` | Pool is *larger* than the thread cap, so the pool is **not** the first thing to exhaust. |
| **No `statement_timeout`, no `connect_timeout`, no `pool_timeout`** | `chafan_core/db/session.py` | A slow query can pin a worker thread **indefinitely**. |
| **Redis client has no `socket_timeout`** | `chafan_core/app/common.py:get_redis_cli` (`max_connections=60`) | Redis is on every request's hot path (cache + rate limiter). A slow Redis blocks a thread with no upper bound. |
| **Behind a Cloudflare tunnel** | `scripts/launch_serv/5_cloudflared_screen.sh` (`cloudflared`) | Origin (`127.0.0.1:8000`) is **not publicly exposed**; all traffic arrives via Cloudflare, which sets `CF-Connecting-IP`. Cloudflare's origin timeout is ~100s → **524** to the client. |
| **Rate limiter trusts client-supplied `X-Forwarded-For`** | `chafan_core/app/common.py:client_ip` (takes first XFF entry); `limiter.py` (`150/minute`) | A client can prepend a fake XFF; Cloudflare *appends* to it, so the first entry is attacker-controlled → **the 150/min cap is bypassable**. |

### The failure mechanism

Under a crawler storm, the binding constraint is the **40-thread pool**, not the
DB pool:

1. All ~40 threads become busy serving bot requests.
2. Each thread does DB + Redis I/O with **no upper time bound**. One slow query
   or a degraded Redis pins its thread.
3. Incoming requests **queue** for a thread token. Queue latency climbs.
4. Requests sit until Cloudflare's ~100s origin timeout fires → **524 / "timeout"**,
   or an internal wait surfaces as a `500`. The smoke suite, competing for the
   same saturated pool, catches the timeout as collateral damage.

The earlier hypothesis (DB connection-pool exhaustion) is **secondary**: with a
single process capped at ~40 concurrent threads, we rarely check out more than
~40 of the 80 connections. The dominant variable is **how long each thread is
held**, which today is **unbounded**.

---

## 3. Design principle

> Make every blocking operation **time-bounded**, so no request can hold a
> worker thread (or a DB/Redis connection) longer than a small, known ceiling.
> Then make the existing per-IP limiter **actually enforceable**. Then scale
> capacity deliberately.

Bounding hold time is the highest-leverage change: it turns "one slow
dependency takes the whole origin down" into "slow requests fail fast and free
their thread," which lets the pool drain and recover on its own.

---

## 4. Proposed changes (prioritized)

### P0 — Bound every I/O wait (behavior-independent; do first)

These protect the origin regardless of who sends the traffic or how many IPs
they use. Small, local, independently revertable.

**4.1 Postgres: cap query and connect time** — `chafan_core/db/session.py`
```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_SESSION_POOL_SIZE,
    max_overflow=settings.DB_SESSION_POOL_MAX_OVERFLOW_SIZE,
    pool_timeout=5,                       # fail fast on checkout instead of waiting 30s
    connect_args={
        "connect_timeout": 5,             # libpq TCP connect ceiling
        "options": "-c statement_timeout=10000",  # 10s hard ceiling per query
    },
)
```
`statement_timeout` is the single most important line: it makes it *impossible*
for any request — bot or not — to pin a thread on a runaway query. Pick the
ceiling from the p99 of legitimate queries (start 10s, tune down).

**4.2 Redis: add socket timeouts** — `chafan_core/app/common.py:get_redis_cli`
```python
_redis_pool = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=60,
    socket_timeout=2,
    socket_connect_timeout=2,
)
```
Redis sits on every request (cache layer + rate-limit storage). An unbounded
Redis wait pins a thread just like a slow query does.

**4.3 Make the ceilings configurable** — add to `config.py:Settings`
```python
DB_STATEMENT_TIMEOUT_MS: int = 10000
DB_POOL_TIMEOUT_SECONDS: int = 5
DB_CONNECT_TIMEOUT_SECONDS: int = 5
REDIS_SOCKET_TIMEOUT_SECONDS: int = 2
```
So ceilings can be tuned per-environment without a code change.

> **Note on outbound HTTP:** the synchronous external calls already have
> timeouts — `request_text` (`cached_layer.py:946`, `timeout=1`), webhook
> (`webhook_utils.py:59`, `timeout=5`), SMTP (`email/smtp_client.py:17`,
> `timeout=30`). The 30s SMTP ceiling is the only worrying one; if email is ever
> sent on a request thread, lower it. (Notification email goes through dramatiq,
> so it is off the request path today — keep it that way.)

### P1 — Make per-IP rate limiting enforceable (closes the XFF bypass)

The `150/minute` limit exists but is bypassable because `client_ip()` trusts
the first client-supplied `X-Forwarded-For` value. Because we sit behind a
**Cloudflare tunnel**, there is a clean, trustworthy source of the real client
IP: the **`CF-Connecting-IP`** header, which Cloudflare sets and a client cannot
forge through the tunnel.

**4.4 Trust `CF-Connecting-IP`** — `chafan_core/app/common.py:client_ip`
```python
def client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    # Fallbacks for local/dev where Cloudflare is absent:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()   # last hop = nearest trusted proxy
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"
```
Two changes: prefer `CF-Connecting-IP`, and for the XFF fallback take the
**last** entry (appended by the nearest trusted proxy) rather than the first
(client-controlled). This makes the `150/min` cap an **enforced** control.

> Defense in depth: ensure the origin only accepts connections from the
> Cloudflare tunnel (already true via `cloudflared` — origin binds `127.0.0.1`).
> That prevents anyone from hitting the origin directly to skip Cloudflare and
> forge headers.

### P2 — Enforced edge rate limiting (mechanical, not cooperative)

Stop the storm before it consumes a worker thread. At Cloudflare (keyed on the
real client IP, which the WAF already knows):

- A **rate-limiting rule** (e.g. N requests / 10s per IP) returning `429`.
- A **per-IP concurrent-connection** cap.
- Optional managed-bot / "definitely automated" challenge for unauthenticated
  read endpoints.

This is the *enforced* version of edge throttling — it does not rely on the bot
honoring anything. **Caveat:** per-IP edge limits degrade against a large
rotating-IP botnet; that is exactly why P0 is the real backstop. Edge limits
shave the common case (a few aggressive IPs) so it never reaches the origin.

### P3 — Scale capacity deliberately (only after P0)

Today the origin is one process × ~40 threads. If sustained legitimate
concurrency needs more, raise capacity **in tandem with the connection budget**:

- Raise the anyio threadpool limit, **or** run multiple uvicorn/gunicorn workers.
- Each worker carries its own DB pool (up to 80 connections). `workers × 80`
  must stay safely under Postgres `max_connections` (verify `SHOW
  max_connections;`). With P0's `pool_timeout`, crossing the line fails fast
  instead of hanging — but the goal is to size so it never crosses.
- Reconsider `pool_size=60`: for a ~40-thread process it keeps ~60 idle
  connections open. A pool closer to the thread cap (e.g. 40 + 10 overflow) is
  less wasteful and leaves room for more workers.

Right-sizing is a tuning exercise; do it after P0 with real numbers, not now.

---

## 5. What this explicitly does *not* do

- Does not add `robots.txt` / crawl-delay as a defense (rejected: voluntary).
- Does not rely on `User-Agent` allow/deny lists for protection (spoofable).
- Does not attempt to *identify* or fingerprint individual bots. We contain the
  blast radius instead of winning an identification arms race.

---

## 6. Rollout & verification

1. **Ship P0** behind the new config knobs (default to the values above).
   - Verify: under a synthetic concurrent read flood (e.g. `hey`/`wrk` against a
     staging origin), slow requests now return promptly with errors and the
     origin **recovers** once the flood stops, instead of staying wedged.
   - Verify: a deliberately slow query is cut at `statement_timeout` and its
     thread is released.
2. **Ship P1**, then confirm the rate limiter actually fires per real client IP
   (send >150 req/min from one IP with a spoofed `X-Forwarded-For`; expect
   `429`, not a bypass).
3. **Configure P2** at Cloudflare; watch that legitimate users are not caught
   (tune thresholds against real traffic percentiles).
4. **Re-run the smoke suite** (`chafan-smoke-tests`) after each step — it is the
   existing end-to-end signal and will catch regressions in the read/write
   paths. Watch the s10 feed-latency baseline for drift.
5. Revisit **P3** with measured concurrency once P0/P1/P2 are stable.

## 7. Risk & rollback

- All P0/P1 changes are small, local, and gated by config; rollback is a value
  change or a revert of a few lines.
- Main risk in P0 is a **too-aggressive `statement_timeout`** killing a
  legitimate slow endpoint. Mitigate by setting the ceiling from observed p99
  and tuning down gradually; the knob makes this a config change, not a deploy.
- Main risk in P1 is **mis-reading the client IP** (rate-limiting everyone as
  one IP, or re-opening the bypass). Mitigated by preferring `CF-Connecting-IP`,
  which is unambiguous behind the tunnel.

---

## 8. Summary

The origin's real limit under hostile crawler load is a **~40-thread pool whose
threads can be held for an unbounded time** by slow DB/Redis I/O — not DB pool
size. The fix, in order: **(P0)** bound every I/O wait so no thread is ever
pinned; **(P1)** trust `CF-Connecting-IP` so the existing `150/min` limiter
becomes enforceable; **(P2)** add enforced per-IP limits at Cloudflare; **(P3)**
scale workers/threads deliberately against the DB connection budget. None of
this depends on the bot behaving, which is the requirement.
