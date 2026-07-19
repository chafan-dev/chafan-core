# 10: Request Logging Middleware

**Phase:** 2 — Feature-level | **Effort:** Half day | **Risk:** Low

---

## Problem

Request-level visibility is ad-hoc. Some handlers log; most don't. Tracing a specific user's request through the system today requires guessing which handler to instrument.

## Fix

Add a FastAPI middleware that logs every request with a consistent structure. Use the standard library `logging` module (no `structlog` dependency added for this alone — use `extra={}` to attach structured fields).

### Fields to log

- Request ID (generate if absent; echo in response header `X-Request-Id`).
- Method, path, query (query keys only — not values, to avoid PII leaks from search strings etc.).
- Status code.
- Duration (milliseconds).
- Authenticated user ID if present.
- Client IP — **reuse the existing `chafan_core/app/common.py:client_ip` helper** (line 169). Do not duplicate the X-Forwarded-For handling logic. If the helper's behavior needs tightening (e.g. to only trust XFF from known proxy IPs), change `client_ip` itself so every caller benefits — don't fork the logic in the middleware.

### Logger layout

- `chafan.request` — the middleware writes here.
- `chafan.deprecated` — dedicated logger for deprecation warnings (e.g. legacy endpoints that should go away). Add one `logger.warning(...)` at the top of any endpoint we want to flag. Easy to grep; easy to silence or escalate in one place.

### Log format

JSON in prod (structured for later aggregation), plain text in dev (readability). One config setting:

```python
LOG_JSON: bool = False  # prod overrides to True
```

This is not `is_dev()`; it's a direct config value. Dev can opt into JSON logging if desired.

### Body logging: NO

Do not log request or response bodies. Too easy to leak secrets (password resets, login tokens), PII, or just bloat logs. If a future need arises, add a scoped, opt-in mechanism at that time.

## Forward use

- **Phase 4 (`15-image-upload-r2.md`)** emits upload rate-limit decisions and cost-containment killswitch events through these loggers. No new logger scheme needed — Phase 4 adds its own named logger (`chafan.upload` or similar) following the same pattern.
- **Phase 1 (`08-rep-manager-centralization.md`)** uses `chafan.karma_drift` for reconciliation drift logs.
- **Phase 3 (`13-cache-scope-reduction.md`)** uses `chafan.cache` for cache hit/miss sampling during the shrink rollout.

## Acceptance

- Every request produces exactly one line in `chafan.request`.
- `X-Request-Id` appears in responses; if the client supplied one, it's echoed rather than regenerated.
- No bodies logged.
- Dev logs are human-readable; prod logs are JSON.
- A deprecated endpoint produces a warning in `chafan.deprecated` without breaking anything.

## Not in scope

- Centralized log aggregation / shipping (that's ops, not code).
- Distributed tracing (Sentry already captures trace context for errors; we don't need OpenTelemetry spans yet).
