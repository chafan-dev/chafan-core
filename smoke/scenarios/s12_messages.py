"""s12 — private messages.

Synchronous end-to-end: A creates (or reuses) a private channel with B,
A sends a marker, B reads and replies, A reads B's reply.

Channel creation is idempotent
(``crud.channel.get_or_create_private_channel_with``), so re-runs don't
accumulate channels.
"""
from __future__ import annotations

import uuid as uuidlib

from client import ok

TAG = "s12_messages"


def run(state: dict) -> None:
    a = state["a"]
    b = state["b"]

    channel = a.post(
        "/api/v1/channels/",
        {"private_with_user_uuid": b.uuid},
    )
    channel_id = channel["id"]
    ok(TAG, "POST /channels/", f"id={channel_id}")

    marker_a = f"smoke-A-{uuidlib.uuid4().hex[:8]}"
    a.post("/api/v1/messages/", {"channel_id": channel_id, "body": marker_a})
    ok(TAG, "POST /messages/ (A)", f"marker={marker_a}")

    b_view = b.get(f"/api/v1/channels/{channel_id}/messages/")
    assert any(m.get("body") == marker_a for m in b_view), (
        f"B did not see A's marker {marker_a!r} in channel {channel_id}"
    )
    ok(TAG, "B reads channel messages")

    marker_b = f"smoke-B-{uuidlib.uuid4().hex[:8]}"
    b.post("/api/v1/messages/", {"channel_id": channel_id, "body": marker_b})
    ok(TAG, "POST /messages/ (B)", f"marker={marker_b}")

    a_view = a.get(f"/api/v1/channels/{channel_id}/messages/")
    assert any(m.get("body") == marker_b for m in a_view), (
        f"A did not see B's reply {marker_b!r} in channel {channel_id}"
    )
    ok(TAG, "A reads channel messages")


if __name__ == "__main__":
    from scenarios import bootstrap
    run(bootstrap.build_state())
