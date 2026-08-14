# smoke suite

End-to-end smoke test that drives the real HTTP API and exercises every
critical read/write path: auth, questions, answers, comments, submissions,
articles, the follow graph, activity-feed fan-out, notifications, and private
messages. It also asserts the negative paths (`s13_authz`): anonymous writes
and non-author edits/deletes are rejected with the expected status. Exit code
0 = the backend is sane.

`s14_site_create` covers both sides of the one karma-gated action there is:
the low-karma account is refused, the high-karma account creates a site, pays
for it, and then uses it. It depends on account A out-earning
`rules.MIN_KARMA_CREATE_SITE` over the seeded dataset plus the earlier
scenarios; if that ever stops being true the scenario reports SKIP rather than
a hollow pass, which is the signal to seed a dedicated high-karma account.

`s15_upload` is the executable spec for image upload, written *before* the
endpoint exists. It reports XFAIL (known failure) on each spec point the
backend does not yet satisfy, so the PR that adds it is a spec review rather
than a behaviour change; it flips to OK as the implementation lands. The
object-store-dependent points are SKIPped when no object store is configured
(`UPLOADS_S3_*` unset), so a bootstrap run without MinIO does not report false
passes.

The suite reads `config.json` (git-ignored) for the target endpoint and two
member accounts, then runs the scenarios in `scenarios/` fail-fast.

## Two modes

### Bootstrap (CI)

Invents everything it needs against a throwaway dev database — no secrets, no
pre-existing data. `seed.py` populates two users, a public site both belong to,
an article column, and a seed question, then writes `config.json` pointing at a
local server. This is what `.github/workflows/e2e-smoke.yml` runs via
`scripts/e2e/run_e2e_smoke.sh`.

Locally, from the repo root inside the nix devShell with Postgres + Redis up:

```
source env.ci
./scripts/e2e/run_e2e_smoke.sh
```

### Real world (manual)

Hits a real deployment (e.g. `https://api.cha.fan`) with real accounts to
answer "I just deployed — is prod sane?". This is **not** run in CI: it needs
production credentials and leaves artifacts in the real database.

```
cp config.example.json config.json
$EDITOR config.json     # real endpoint + two accounts + a known site/column/question
python run_all.py
```

Both accounts must be members of `site`, and `article_column_uuid` must be
owned by account A.

## Debugging

`DEBUG=1 python run_all.py` prints every HTTP call. Run a single scenario with
`python -m scenarios.s10_feed_fanout` (auto-bootstraps login from `config.json`).
