# 07: Test Hygiene (Good-State Rule, Bug Fixes, Refactor-Driven Test Rewrites)

**Phase:** 1 — Code correctness | **Effort:** 1 day | **Risk:** Low

---

## Honest assessment of the current test suite

As of 2026-04-18, `chafan-core/chafan_core/tests/`:

- **39 test files**, **~401 test functions**.
- **10 skipped tests** (~2.5%). Some skips are due to shared mutable state across module-scoped fixtures (one test creates a row, the next test fails because the row already exists). Others are genuine TODOs.
- **14 TODO/FIXME markers** in test code. These document real bugs the author noticed but did not fix.
- **65 `db.expire_all()` calls** scattered across tests. This is not a bug in itself — it's a workaround for ORM session cache returning stale rows after writes. The high count means we routinely fight the session cache; it's a structural smell.

Concretely: "red is normal" is the accepted status quo. CI failures from flaky test interaction are common enough that a retry is the default reaction, not investigation. We are explicitly choosing not to invest in fixing this until the prod-side work in v2 lands.

This proposal does **not** try to reverse that decay or set a tripwire to detect it. The decay is the agreed baseline.

## Scope changes from v1

v1 Proposal 05 invested in test isolation infrastructure (SAVEPOINT per test, drop-and-recreate fixtures). v2 does **not**. Rationale:

- Production code maintenance takes priority. When prod is stable, we revisit how tests are written.
- The existing test suite is limited; sweeping isolation changes benefit a small surface.
- v1's proposed `db.bind = connection` + `transaction.begin()` pattern is actively wrong — an inner `commit()` ends the outer transaction, breaking the rollback guarantee. Building on that is not the investment v2 wants.

## What v2 adopts instead

### The good-state rule

Any new test case must work on a **good-state database**:

- Schema-valid.
- With or without data (both are good states).
- No orphaned rows, no missing required fields, no broken FK constraints.

This is the bar. New tests must either start from empty or explicitly set up what they need. Tests that assume leftover state from previous tests are not in good standing and should be rewritten when convenient.

We accept that some existing tests may be flaky for that reason. We'll rewrite them as they cause problems, not preemptively.

### Prod-first principle

We prioritize production code correctness over test suite improvements. If a choice is:

- Fix a bug in a handler (prod) vs. add isolation infrastructure (tests) → fix the bug.
- Fix a bug in a handler (prod) vs. rewrite a flaky test (tests) → fix the bug first; rewrite the test only if it's blocking the fix.

When v2 is complete and prod is healthy, we reconsider test infrastructure.

### Refactor-driven test rewrites (the main forward-looking rule)

When a refactor lands (e.g. `08-rep-manager-centralization.md` reroutes karma writes; `13-cache-scope-reduction.md` reshapes cached payloads; `14-n-plus-one-with-link-preview.md` collapses `*ForVisitor` schemas), tests written against the old shape will break. **Rewrite the affected tests as part of the refactor PR. Do not preserve the old tests by working around them in production code.**

This is the primary forward-looking guidance from this proposal. Concretely:

- Old tests are not contracts. They were written against a code shape that no longer exists; they have no claim on the refactor.
- A refactor PR that rewrites 20 affected tests is healthy. A refactor PR that leaves the production code uglier to keep 20 old tests passing is not.
- The new tests must satisfy the good-state rule (above). They do not need to mirror the structure of the tests they replace.
- If rewriting the tests is too large to fit in the same PR, delete the old tests in the refactor PR and file a follow-up to add the new ones. A red-but-honest test surface beats a green-but-misleading one.

This is the operational meaning of README principle 1 ("Be prepared to rewrite old tests").

## What this proposal does include

The inline bug fixes that were the actual value of v1 Proposal 05:

### B1. Endpoint null-deref / schema-drift bugs

Several endpoints dereference optional fields without null-checking, or rely on schema shapes that have drifted. Fix them inline:

- Grep for `.one_or_none()` followed by attribute access without a None check.
- Grep for Pydantic schemas whose fields no longer exist on the underlying model.
- Each such bug becomes its own small commit.

### B2. Test fixtures that violate the good-state rule

Audit `conftest.py` and fixtures. Any fixture that leaves orphaned data or schema-invalid state gets fixed. Fixtures that require a specific pre-existing row (rather than creating it) are rewritten to create their own dependencies.

### B3. Flaky test cleanup (opportunistic)

Not a sweep. When a specific test is flaky and you're touching the area anyway, rewrite it to match the good-state rule. Otherwise leave it.

---

## What this proposal explicitly does NOT do

- No SAVEPOINT-based per-test rollback.
- No drop-and-recreate-DB fixtures.
- No transaction-per-test infrastructure.
- No systematic rewrite of the test suite.

If a future proposal needs transactional test isolation (e.g. the deferred Unit of Work work), it owns bringing that infrastructure.

## CI note

CI already spins a fresh Postgres container per job (`chafan-core/.github/workflows/main-test.yml`). That's sufficient isolation at the job level. Per-test isolation is not currently worth the complexity.

## Acceptance

- Inline bug fixes land.
- Fixtures produce good-state DBs.
- The prod-first principle is documented in the repo (either here or in CLAUDE.md / CONTRIBUTING).
- No new test-isolation infrastructure.
