# smoke suite

End-to-end smoke test that drives the real HTTP API and exercises every
critical read/write path: auth, questions, answers, comments, submissions,
articles, the follow graph, activity-feed fan-out, notifications, and private
messages. It also asserts the negative paths (`s13_authz`): anonymous writes
and non-author edits/deletes are rejected with the expected status. Exit code
0 = the backend is sane.

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
