"""wait_for(): poll a predicate until truthy or timeout, printing elapsed time."""
from __future__ import annotations

import time
from typing import Any, Callable


class PollTimeout(RuntimeError):
    def __init__(self, desc: str, elapsed: float, last: Any):
        super().__init__(
            f"{desc}: timeout after {elapsed:.1f}s\n  last response: {last!r}"
        )
        self.desc = desc
        self.elapsed = elapsed
        self.last = last


def wait_for(
    predicate: Callable[[], Any],
    *,
    timeout: float,
    interval: float = 0.5,
    desc: str,
) -> tuple[Any, float]:
    """Call predicate() repeatedly until it returns truthy or timeout elapses.

    Returns (result, elapsed_seconds) on success.
    Raises PollTimeout on failure, including elapsed time and the last return value.
    """
    start = time.monotonic()
    last: Any = None
    while True:
        last = predicate()
        elapsed = time.monotonic() - start
        if last:
            return last, elapsed
        if elapsed >= timeout:
            raise PollTimeout(desc, elapsed, last)
        time.sleep(interval)
