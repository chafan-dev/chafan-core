#!/usr/bin/env python3
"""Driver: run every smoke scenario in order, fail-fast on the first exception.

Usage:
    python run_all.py
    DEBUG=1 python run_all.py
"""
from __future__ import annotations

import sys
import traceback

from scenarios import bootstrap
from scenarios import (
    s01_auth,
    s02_read_only,
    s03_question,
    s04_answer,
    s05_comment,
    s06_submission,
    s07_article,
    s09_follow,
    s10_feed_fanout,
    s11_notifications,
    s12_messages,
    s08_delete,
)

# Order matches SMOKE_TEST_PLAN.md § "Scenario order note".
# s08_delete runs absolutely last so s11 still has A's question/answer.
SCENARIOS = [
    s01_auth,
    s02_read_only,
    s03_question,
    s04_answer,
    s05_comment,
    s06_submission,
    s07_article,
    s09_follow,
    s10_feed_fanout,
    s11_notifications,
    s12_messages,
    s08_delete,
]


def main() -> int:
    try:
        state = bootstrap.build_state()
    except Exception as e:
        print(f"bootstrap failed: {e}")
        return 1

    for scenario in SCENARIOS:
        try:
            scenario.run(state)
        except Exception as e:
            print(f"FAIL  {scenario.__name__}: {e}")
            if __debug__ and sys.stderr.isatty():
                traceback.print_exc()
            return 1

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
