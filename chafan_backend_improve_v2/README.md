# chafan Backend Improvement Plan — v2

This supersedes `chafan_backend_improve/`. v1 remains in-place as reference; do not delete.

## Scope

Refactoring, cleanup, and targeted feature work across the chafan-core backend plus three bundled feature rewrites:
- Cache scope reduction (big refactor)
- Link Preview backend collapse (bundled with N+1 fixes)
- Image upload → Cloudflare R2 rewrite
- Karma/coin centralization via `rep_manager`

Out of scope: PWA frontend work, Vue 3 migration.

## Guiding principles

1. **Prod-first.** Maintenance of production code takes priority over tests. When prod is stable, revisit how tests are written. Be prepared to rewrite old tests.
2. **Good-state rule.** Any new test case must work on a good-state DB — schema-valid, with or without data, no conflicts, no missing required fields. This is the bar; test-isolation infrastructure is not.
3. **Measure before optimizing.** Performance proposals (N+1, cache shrink) require per-endpoint measurement before applying the fix; no shotgun refactors.
4. **Dev/prod parity by default.** Replace `is_dev()` behavior switches with explicit config flags defaulting to the same value in all environments. Known exception: the image upload path stays diverged from when `06-dev-prod-unification.md` ships until `15-image-upload-r2.md` ships (Phase 4 is intentionally late). Accepting this gap is the cost of not rushing the upload rewrite.
5. **One responsibility per module.** `rep_manager` owns karma + coin mutations. Centralize, then iterate.
6. **Cache only heavy work.** Backend Redis cache is for heavy cross-joins and materialized payloads. Indexed single-row reads do not need caching; that was an AWS-era cost optimization no longer load-bearing.
7. **Avoid DB schema migrations unless really necessary.** Schema changes are expensive to revert and cross-cut deployment, ORM models, and frontend assumptions. Prefer code-level workarounds, freezing unused columns, or behavior changes over `ALTER TABLE`. If a proposal needs a migration, it must justify why no code-only path works.

## Phase layout

| Phase | Theme | Risk | Contents |
|-------|-------|------|----------|
| 0 | Quick wins | Low | README, Makefile + Poetry/Dokku removal, password policy, grammar, scheduled-task consolidation |
| 1 | Code correctness | Low–Medium | Fake async cleanup, dev/prod unification, test hygiene, rep_manager centralization, seed unification |
| 2 | Feature-level | Medium | Adaptive search index rebuild, request logging, OpenAPI baseline |
| 3 | Big refactors | Medium–High | Cache scope reduction + invalidation redesign, N+1 fixes bundled with Link Preview backend |
| 4 | Image upload rewrite | Medium | R2 migration + dev/prod unification (cost-containment stack parked in `deferred/`) |
| 5 | Optional formula tuning | Low | Deferred karma formula tweaks — document only, do not ship unless demand emerges |

Phases are ordered for typical sequencing; within a phase, proposals are mostly independent. No hard cross-phase dependencies remain in the core Phase 4 scope after the `15` scope reduction — the APScheduler / coin-hook dependencies moved with the canary/coin features to `deferred/upload-cost-containment.md`. Phase 1's `rep_manager` contract is still the intended coin-routing path if/when that deferred work is revived.

## Proposal index

### Phase 0 — Quick wins
- `proposals/00-readme-cleanup.md`
- `proposals/01-makefile-cleanup.md`
- `proposals/02-password-policy.md`
- `proposals/03-grammar-fixes.md`
- `proposals/04-scheduled-consolidation.md`

### Phase 1 — Code correctness
- `proposals/05-fake-async-cleanup.md`
- `proposals/06-dev-prod-unification.md`
- `proposals/07-test-hygiene.md`
- `proposals/08-rep-manager-centralization.md`
- `proposals/12-seed-unification.md` (owns the former `06` A7 and the broader UUID-env-var cleanup)

### Phase 2 — Feature-level
- `proposals/09-adaptive-search-index.md`
- `proposals/10-request-logging.md`
- `proposals/11-openapi-baseline.md`

### Phase 3 — Big refactors
- `proposals/13-cache-scope-reduction.md`
- `proposals/14-n-plus-one-with-link-preview.md`
- `proposals/16-measurement-infra-needed.md` (placeholder — documents the measurement gap that 13 and 14 need filled)

### Phase 4 — Image upload
- `proposals/15-image-upload-r2.md`

### Phase 5 — Optional formula tuning (deferred)
- `phase5-optional/16a-featured-bonus.md`
- `phase5-optional/16b-time-decay.md`
- `phase5-optional/16c-concentration-penalty.md`
- `phase5-optional/16d-provisional-trust.md`

### Deferred / under review
- `deferred/async-migration.md` — "should we?" gate, decide after v2 lands
- `deferred/unit-of-work.md` — stands on its own merits; revisit after test hygiene lands
- `deferred/errormsg-strenum.md` — dropped unless maintenance pain becomes concrete
- `deferred/per-site-karma-sort.md` — Profile.karma frozen by `08`; revisit if a modder requests per-site ordering
- `deferred/upload-cost-containment.md` — 5-layer rate limit / killswitch / canary stack split off from `15`; revisit after R2 is live

### Shared knowledge (status-quo snapshots)
- `knowledge/scheduler-status-quo.md` — APScheduler + Dokku cron state as of 2026-04-19. Referenced by `04`, `09`, `15`.

## What changed from v1

**Dropped:**
- Test isolation infrastructure (SAVEPOINT, drop-and-recreate). Replaced with the good-state rule and prod-first principle.
- Proposal 06 (conftest split).
- Proposal 09 (ErrorMsg StrEnum refactor).
- Proposal 11B (systematic error-path tests).

**Deferred:**
- Proposal 12 Part A (full async migration).
- Proposal 12 Part B (Unit of Work).
- v2-draft Proposal 12 (per-site karma sort) — `Profile.karma` frozen by `08`.

**Split or reshaped:**
- v1 Proposal 07 A1 (enable cache in dev) absorbed into v2's larger cache scope reduction.
- v1 Proposal 07 A6 (upload dev/prod gap) superseded by Phase 4 image upload rewrite.
- v1 Proposal 07 A7 (welcome-form UUID bypass) extracted into `12-seed-unification` — the broader UUID-env-var cleanup.
- v1 Proposal 10 (N+1) bundled per-resource with Link Preview's materializer collapse.
- `15-image-upload-r2` scope reduction: R2 migration + dev/prod unification only; cost-containment stack (rate limit layers, killswitch, canary) split off to `deferred/upload-cost-containment`.

**Added:**
- `04-scheduled-consolidation` — migrates remaining Dokku cron jobs into the APScheduler instance that's already running in `main.py`.
- `08-rep-manager-centralization` — from `KARMA_OVERHAUL_PLAN.md`; adds coin mutation routing.
- `09-adaptive-search-index` — Redis point-counter for full rebuild triggering.
- `12-seed-unification` — centralize DB seeding, delete UUID-shaped env params.
- `13-cache-scope-reduction` — shrink cache to heavy cross-joins, redesign invalidation.
- `14-n-plus-one-with-link-preview` — bundles Link Preview backend B1-B14 with eager-loading.
- `15-image-upload-r2` — adopts `image_upload_plan.md` (R2 + dev/prod unification only; cost-containment parked).
- Phase 5 optional formula tuning — from KARMA_OVERHAUL_PLAN.md Phase 4.
- `knowledge/scheduler-status-quo.md` — captured current APScheduler / Dokku-cron state so `04` can stop re-deriving it.
- `deferred/upload-cost-containment.md` — parked abuse-containment design split off from `15`.
