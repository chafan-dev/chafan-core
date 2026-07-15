#!/usr/bin/env python3
"""Poll an HTTP endpoint until it answers 2xx or a timeout elapses.

Used by the e2e smoke workflow to gate on the live uvicorn server being
ready before the smoke suite starts. Exit 0 = ready, 1 = timed out.

Usage:
    python scripts/e2e/wait_ready.py <url> [timeout_seconds]
"""
from __future__ import annotations

import sys
import time

import requests


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: wait_ready.py <url> [timeout_seconds]", file=sys.stderr)
        return 2
    url = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

    start = time.monotonic()
    last_err = "no attempt made"
    while time.monotonic() - start < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.ok:
                print(f"ready after {time.monotonic() - start:.1f}s ({url})")
                return 0
            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
        time.sleep(1)

    print(
        f"not ready after {timeout:.0f}s ({url}): {last_err}", file=sys.stderr
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
