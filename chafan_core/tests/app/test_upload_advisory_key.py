"""Key derivation for the per-sha advisory lock that stops double-charging.

The lock itself needs two concurrent sessions against Postgres to exercise;
what is checkable without a database is that the key is stable, in range for
a Postgres bigint, and actually discriminates between shas.
"""

import hashlib

from chafan_core.app.crud.crud_upload import advisory_key

PG_BIGINT_MAX = 2**63 - 1


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_key_fits_a_signed_bigint():
    # pg_advisory_xact_lock takes a signed 64-bit key; a value outside that
    # range is an error, not a silently wrapped lock.
    for seed in ("a", "b", "ffff", "the quick brown fox", ""):
        key = advisory_key(_sha(seed))
        assert 0 <= key <= PG_BIGINT_MAX


def test_key_is_stable_for_the_same_sha():
    sha = _sha("same bytes")
    assert advisory_key(sha) == advisory_key(sha)


def test_key_separates_different_shas():
    keys = {advisory_key(_sha(str(i))) for i in range(500)}
    # 60 bits over 500 samples: a collision here would mean the derivation is
    # not using the entropy it claims to.
    assert len(keys) == 500


def test_key_uses_60_bits_of_the_sha():
    sha = "0" * 15 + "f" * 49
    assert advisory_key(sha) == 0
    sha = "f" * 15 + "0" * 49
    assert advisory_key(sha) == 2**60 - 1
