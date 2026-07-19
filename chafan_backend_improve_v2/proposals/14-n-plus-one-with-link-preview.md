# 14: N+1 Fixes Bundled with Link Preview Backend Collapse

**Phase:** 3 — Big refactors | **Effort:** 2-4 weeks | **Risk:** Medium

> Effort bumped from the initial 1-2 week estimate once three realities became clear: the per-resource measurement loop is genuinely slower than a blind-pass refactor; the `*ForVisitor` schema family has 123 references across 22 files; and the `Profile.user` eager-load ripple (see Part C below, caused by `08`'s freeze of `Profile.karma`) adds one more pass that wasn't in the original scope.

**Source plans:** `/var/home/lizhenbo/src/chafan/LINK_PREVIEW_FIX_PLAN.md` (Backend steps B1-B14), original v1 `proposals/10-n-plus-one.md`.

**Depends on:** `13-cache-scope-reduction.md` (cache scope must be settled before reshaping materialized payloads).

---

## Bundling rationale

Two separate v1 proposals:
1. Fix N+1 query problems across the materialization layer.
2. Collapse the `*ForVisitor` schema family (and their materializers, cache keys) so link-preview metadata renders correctly without auth.

Both touch the same code (`materialize.py`, answer/question/article CRUD, `cached_layer.py`) and both benefit from one pass per resource. Bundling avoids touching each file twice.

## Scope

### Part A — Link Preview backend (from LINK_PREVIEW_FIX_PLAN.md B1-B14)

Collapse the `*ForVisitor` schema/materializer/cache-key family into the standard schemas, adjusting visibility logic inline instead of via duplicated code paths. This produces correct OpenGraph tag data for unauthenticated scrapers (Twitter, Discord, etc.).

Follow LINK_PREVIEW_FIX_PLAN.md's backend B-steps in order. No changes to that plan's structure; reference it directly for step-by-step.

### Part B — N+1 fixes, per resource

Rather than a shotgun pass across all of `materialize.py`, work one resource at a time:

1. Pick a resource (question, answer, article, submission, comment tree).
2. Measure the endpoint's query count with `SQLALCHEMY_ECHO=true` or a per-request query counter.
3. Add appropriate eager loading to the CRUD method that fetches the resource:
   - `selectinload` for to-many collections (answers, comments, bookmarkers) — avoids cartesian product.
   - `joinedload` for to-one relationships (e.g. `Answer.question`, `Answer.author`) — one JOIN, no row explosion.
4. Re-measure. Verify query count dropped and that the cached materialized payload still serializes correctly.
5. Move to the next resource.

### Bundling per resource

Each resource (question, answer, article, etc.) gets one PR that:
- Does its N+1 fix.
- Does its share of the Link Preview `*ForVisitor` collapse.
- Re-measures and verifies.

This is slower than "one big cleanup PR" but dramatically lower risk and easier to review/revert.

### Part C — `Profile.user` eager-load ripple (from `08`)

`08-rep-manager-centralization.md` freezes `Profile.karma` and rewrites every reader to sort by `User.karma DESC, User.id ASC`. Known affected call site: `chafan_core/app/recs/ranking.py:69-70` (`rank_site_profiles`). Any other sort/read of `Profile.karma` found during the `08` grep pass is on this list too.

Without eager-loading, the swap from `p.karma` to `p.user.karma` turns a single indexed read into N+1: one query per profile to fetch `Profile.user`. This proposal owns the fix:

1. For each affected sort path, add `joinedload(Profile.user)` (one JOIN; profiles:users is many-to-one).
2. Re-measure query count before/after.
3. Verify the sort ordering is stable (ties broken by `User.id ASC`).

Timing: land this part **after** `08` has done the `p.karma` → `p.user.karma` swap. If `14` starts before `08`, defer Part C until `08` merges.

## Approach

Measurement before changes:

1. Enable `SQLALCHEMY_ECHO=true` in dev (ad-hoc) or use the per-request query counter middleware from `16-measurement-infra-needed.md` (preferred — attributes queries to endpoints). The middleware does not exist yet; if `14` starts before it's built, this proposal owns the minimum viable version.
2. Hit each candidate endpoint with representative data.
3. Record baseline query counts.

Candidate endpoints (in v1 Proposal 10's list):

| Location | Pattern |
|----------|---------|
| `materialize.py` 540, 571 | `article.comments` loop |
| `materialize.py` 782, 820 | `answer.comments` loop |
| `materialize.py` 873, 908 | `question.comments` loop |
| `materialize.py` 932, 962 | `submission.comments` loop |
| `materialize.py` 573, 826 | `.bookmarkers.count()` |
| `api/endpoints/questions.py` 38, 52 | `question.answers` preview |
| `cached_layer.py` 733, 740, 805 | `author.answers` loop |
| `task.py` 743-744 | `a.question.title` in loop during search index refresh |

## Principles

- **Measure per endpoint.** "No `selectinload` anywhere" is a smell, not a bug report. Not every N+1 is hurting users.
- **`selectinload` for collections, `joinedload` for to-one.** Don't cargo-cult `selectinload` everywhere — for `Answer.question` (many-to-one), `joinedload` is preferable.
- **Beware of interactions with the cache.** Post-`13-cache-scope-reduction.md`, some previously-cached joins are now direct queries. Eager-loading them is now useful; before the cache refactor, it was redundant. That's why this proposal depends on `13`.

## Acceptance

- Each touched endpoint has measured before/after query counts recorded in the PR description.
- Regression tests (or at minimum manual verification) confirm cached payloads serialize correctly post-refactor.
- Link Preview: a request from an unauthenticated scraper (test via curl or a tag-preview tool) returns correct OG tags for questions, answers, articles.
- No `*ForVisitor` schemas remain.
- `Profile.user` eager-load applied to every sort path that `08` rewrote from `Profile.karma` to `User.karma` (verified by grep for the post-`08` sort pattern).

## Dependencies

- `13-cache-scope-reduction.md` — must land first (Parts A and B).
- `08-rep-manager-centralization.md` — Part C depends on `08` landing first; Parts A/B are independent.

## Risks

- **Large collection eager-load turning one cheap query into one expensive one.** Mitigation: per-endpoint measurement, not blind `selectinload`.
- **Cache invalidation interactions.** Mitigation: verify the cached payload key covers the eagerly-loaded fields; ensure version-key invalidation (from `13`) covers mutations to those fields.
