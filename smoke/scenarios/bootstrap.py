"""Shared bootstrap so single-scenario runs can auto-login.

``run_all.py`` calls ``build_state()`` once and threads the result through
every scenario. Individual scenarios, when run via ``python -m scenarios.sXX``,
also call ``build_state()`` from their ``__main__`` block.
"""
from __future__ import annotations

import sys
import pathlib

# Allow `python -m scenarios.sXX` from inside the scenarios/ dir.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client import ApiClient, load_config, parse_site_subdomain, ok  # noqa: E402


def build_state() -> dict:
    cfg = load_config()
    a = ApiClient(cfg["api_base"], "A")
    b = ApiClient(cfg["api_base"], "B")
    a.login(cfg["account_a"]["username"], cfg["account_a"]["password"])
    b.login(cfg["account_b"]["username"], cfg["account_b"]["password"])

    subdomain = parse_site_subdomain(cfg["site"])
    site = a.get(f"/api/v1/sites/{subdomain}")
    site_uuid = site["uuid"]
    cfg["site_uuid"] = site_uuid
    ok("bootstrap", f"resolved site {subdomain!r}", f"uuid={site_uuid}")

    return {"cfg": cfg, "a": a, "b": b}
