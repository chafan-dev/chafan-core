"""Smoke test scenarios.

Each module exposes a `run(state)` function. `state` is a dict shared across
scenarios and carries the logged-in ApiClient instances and uuids captured
by earlier scenarios.

Running a scenario file directly (``python -m scenarios.s10_feed_fanout``)
auto-bootstraps via bootstrap.build_state(), which logs in both accounts.
"""
