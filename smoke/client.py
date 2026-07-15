"""Thin wrapper around requests.Session for the smoke suite.

One ApiClient per account. Holds the JWT in memory for the run.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Optional

import requests

DEBUG = bool(os.environ.get("DEBUG"))


class ApiError(RuntimeError):
    pass


def load_config() -> dict:
    path = pathlib.Path(__file__).parent / "config.json"
    if not path.exists():
        raise ApiError(
            f"{path} not found. Copy config.example.json to config.json and fill it in."
        )
    with path.open() as f:
        cfg = json.load(f)
    required = [
        "api_base",
        "site",
        "article_column_uuid",
        "known_question_uuid",
        "poll_timeout_seconds",
        "account_a",
        "account_b",
    ]
    for key in required:
        if key not in cfg:
            raise ApiError(f"config.json missing required field: {key}")
    for acct in ("account_a", "account_b"):
        for sub in ("username", "password"):
            if sub not in cfg[acct]:
                raise ApiError(f"config.json missing {acct}.{sub}")
    return cfg


def parse_site_subdomain(site_value: str) -> str:
    """Extract subdomain from a site URL or bare subdomain.

    Accepts:
      - "cha.fan/sites/meaningless"
      - "https://cha.fan/sites/meaningless"
      - "meaningless"  (bare subdomain)
    """
    site_value = site_value.strip().rstrip("/")
    if "/sites/" in site_value:
        return site_value.split("/sites/")[-1].split("/")[0]
    return site_value


class ApiClient:
    def __init__(self, api_base: str, label: str):
        self.api_base = api_base.rstrip("/")
        self.label = label
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.uuid: Optional[str] = None
        self.handle: Optional[str] = None
        self.full_name: Optional[str] = None

    # ---- HTTP helpers -------------------------------------------------

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.api_base}{path}"

    def _headers(self, authed: bool = True) -> dict:
        h = {"Accept": "application/json"}
        if authed and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _raise(self, method: str, path: str, resp: requests.Response) -> None:
        body = resp.text
        if len(body) > 800:
            body = body[:800] + "... [truncated]"
        raise ApiError(
            f"{method} {path} → {resp.status_code}\n  body: {body}"
        )

    def _log(self, method: str, path: str, status: int) -> None:
        if DEBUG:
            print(f"  [{self.label}] {method} {path} → {status}")

    def get(self, path: str, **params: Any) -> Any:
        resp = self.session.get(
            self._url(path), headers=self._headers(), params=params or None
        )
        self._log("GET", path, resp.status_code)
        if not resp.ok:
            self._raise("GET", path, resp)
        return resp.json()

    def anonymous_get(self, path: str, **params: Any) -> Any:
        resp = self.session.get(
            self._url(path), headers=self._headers(authed=False), params=params or None
        )
        self._log("GET(anon)", path, resp.status_code)
        if not resp.ok:
            self._raise("GET(anon)", path, resp)
        return resp.json()

    def post(self, path: str, json_body: Optional[dict] = None) -> Any:
        resp = self.session.post(
            self._url(path), headers=self._headers(), json=json_body
        )
        self._log("POST", path, resp.status_code)
        if not resp.ok:
            self._raise("POST", path, resp)
        if resp.text:
            return resp.json()
        return None

    def put(self, path: str, json_body: Optional[dict] = None) -> Any:
        resp = self.session.put(
            self._url(path), headers=self._headers(), json=json_body
        )
        self._log("PUT", path, resp.status_code)
        if not resp.ok:
            self._raise("PUT", path, resp)
        if resp.text:
            return resp.json()
        return None

    def delete(self, path: str) -> Any:
        resp = self.session.delete(self._url(path), headers=self._headers())
        self._log("DELETE", path, resp.status_code)
        if not resp.ok:
            self._raise("DELETE", path, resp)
        if resp.text:
            return resp.json()
        return None

    # ---- Auth ----------------------------------------------------------

    def login(self, username: str, password: str) -> None:
        """Form-encoded login via OAuth2PasswordRequestForm."""
        if DEBUG:
            print(f"  [{self.label}] login as {username!r}")
        resp = self.session.post(
            self._url("/api/v1/login/access-token"),
            data={"username": username, "password": password},
            headers={"Accept": "application/json"},
        )
        self._log("POST", "/api/v1/login/access-token", resp.status_code)
        if not resp.ok:
            self._raise("POST", "/api/v1/login/access-token", resp)
        self.token = resp.json()["access_token"]

        me = self.get("/api/v1/me")
        for field in ("uuid", "handle"):
            if field not in me or not me[field]:
                raise ApiError(f"GET /api/v1/me missing field: {field}")
        self.uuid = me["uuid"]
        self.handle = me["handle"]
        self.full_name = me.get("full_name")


def richtext(body: str) -> dict:
    """Build a RichText payload the backend accepts."""
    return {"source": body, "editor": "wysiwyg", "rendered_text": body}


def ok(prefix: str, label: str, extra: str = "") -> None:
    """Print an OK line, fixed-width for readability."""
    line = f"[{prefix:<12}] {label:<34} OK"
    if extra:
        line += f"   {extra}"
    print(line)
