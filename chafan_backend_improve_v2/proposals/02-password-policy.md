# 02: Password Policy Consolidation

**Phase:** 0 — Quick wins | **Effort:** 1 hour | **Risk:** Low

---

## Problem

Password validation is duplicated across signup/reset/change-password handlers with slightly different rules (different minimum lengths, inconsistent character-class requirements).

## Fix

1. Add a single `validate_password(pw: str) -> None` helper that raises a domain-specific exception on violation. Put it next to the auth code.
2. Replace every password-validation block at the call sites with a call to this helper.
3. Define the policy as a single source of truth: minimum length, required character classes, max length (to avoid DoS via bcrypt input size).
4. Unit-test the helper directly. No need to test each call site separately.

## Decision (policy values)

- Min length: 8
- Max length: 72 (bcrypt input limit)
- No character-class requirement beyond length (length beats composition rules in modern guidance)

If different classes are desired, configure them in the helper — not at the call sites.

### Note on the 72-byte max

The 72-byte limit has been in place for a long time and continues to serve us well. Some newer bcrypt implementations (and bcrypt variants like bcrypt-long) support longer inputs by pre-hashing, but we deliberately keep the limit at 72 bytes. Reasons:

- It matches the canonical bcrypt behavior — no dependence on variant-specific pre-hashing that could diverge across libraries or versions.
- It caps DoS exposure: a 1 MB "password" never reaches bcrypt's hashing loop.
- Users with existing sub-72-byte passwords are unaffected; nobody is currently hitting the cap in practice.

Do not raise the limit without a concrete user-visible reason, and do not lower it — both are unforced breaking changes.

## Acceptance

- All password validation flows through one helper.
- Changing the policy means editing one function.
