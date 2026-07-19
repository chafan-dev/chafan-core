# Phase 5 — Optional Formula Tuning (Deferred)

These four proposals capture the design for optional karma formula improvements from `KARMA_OVERHAUL_PLAN.md` Phase 4.

**Do not ship any of them as part of v2** unless a specific, concrete demand emerges. They're documented so the design work isn't lost; implementation is gated on observed need.

Each proposal is independent. None depends on the others. All assume `08-rep-manager-centralization.md` has landed.

## Triggers for picking one up

| Proposal | Trigger |
|----------|---------|
| 16a — Featured bonus | Site owners repeatedly ask for a way to elevate specific answers without manual karma grants |
| 16b — Time decay | Top-karma users are dominated by early adopters whose contributions are years old and no longer relevant |
| 16c — Concentration penalty | A single viral answer farms disproportionate karma; spammer exploits this vector |
| 16d — Provisional trust | New-user signal quality is poor; we need ramp-up before full karma privileges unlock |

If none of these triggers fire, this phase stays deferred indefinitely.

## Review cadence

These four files are not on a calendar review. They are reviewed **when (if) Phase 5 begins** — i.e. when Phases 0-4 are done and there's a concrete reason to revisit karma formula tuning. Until that point, they sit dormant by design. A file lingering here is not a sign of rot; it's the intended state.
