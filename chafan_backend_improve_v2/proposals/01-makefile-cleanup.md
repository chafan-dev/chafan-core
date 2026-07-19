# 01: Makefile Cleanup + Poetry & Dokku Removal

**Phase:** 0 — Quick wins | **Effort:** 1-2 hours | **Risk:** Low

---

## Problem

`chafan-core/Makefile` contains dead targets and references to tools no longer in use:

- `staging-pr` and `deploy` targets — Dokku-based, broken long ago, not run.
- References to Poetry (`poetry run …`) — we use the Nix flake for environment.
- `app.json` at repo root — Dokku-specific manifest.
- README has a Staging section describing the dead Dokku flow.

Keeping these around is actively misleading to contributors (and to future-me).

## Fix

1. Delete Dokku Makefile targets (`staging-pr`, `deploy`, any Dokku-specific helpers).
2. Remove all Poetry references from Makefile and any scripts; rely on the Nix dev shell.
3. Delete `app.json` at the repo root.
4. Remove the Staging section from README.
5. Delete `scripts/schedule-runner.py` — **this proposal owns the deletion** (replaced by APScheduler — see `04-scheduled-consolidation.md`).

## Decision

Dokku staging is dead. If staging returns, we'll design it fresh against whatever deploy target is live at that point. No half-removal — delete cleanly.

## Acceptance

- `grep -i poetry` and `grep -i dokku` return no hits in the repo (outside of docs describing past history, if any).
- `make` lists only live targets.
- No commit to the repo references `app.json`.

## Note

`scripts/schedule-runner.py` deletion is owned by this proposal (not by `04-scheduled-consolidation.md`). If `04` somehow lands first, the deletion is folded in there and this proposal's step 5 becomes a no-op.
