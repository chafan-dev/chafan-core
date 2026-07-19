# 00: README Cleanup

**Phase:** 0 — Quick wins | **Effort:** 30 min | **Risk:** None

---

## Problem

`chafan-core/README.md` contains stale setup instructions, outdated dependency names, and references to tools we no longer use (Poetry, some Dokku-specific steps).

## Fix

- Remove obsolete sections.
- Update setup instructions to match the current Nix flake + direnv workflow.
- Remove any lingering references to Poetry and Dokku (these die fully in `01-makefile-cleanup.md`).
- Keep the file short — this is a quick-start, not a manual.

## Acceptance

A new contributor following the README can clone the repo, enter the dev shell, and run tests.
