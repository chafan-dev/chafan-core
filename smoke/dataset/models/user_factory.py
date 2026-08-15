"""Create realistic users for the smoke test site.

Produces a mix of superusers, power contributors, casual users, and lurkers.
Each user gets a proper handle, full name, email, and bio that reads like
a real community member profile.
"""

from __future__ import annotations

from chafan_core.app import crud, schemas
from chafan_core.app import karma
from chafan_core.app.coins import award_coins
from chafan_core.utils.validators import StrippedNonEmptyBasicStr, StrippedNonEmptyStr

TARGET_COINS = 1000


# ---------------------------------------------------------------------------
# User definitions -- realistic names, handles, emails, bios
# ---------------------------------------------------------------------------

USERS = [
    {
        "key": "account_a",
        "email": "smoke-a@cha.fan",
        "handle": "smoke_a",
        "full_name": "Alex Chen",
        "password": "smoke-pw-a1",
        "is_superuser": True,
        "bio": "Site moderator. Backend engineer who loves Rust, PostgreSQL, and clean APIs. I started on this platform to share knowledge about distributed systems.",
    },
    {
        "key": "account_b",
        "email": "smoke-b@cha.fan",
        "handle": "smoke_b",
        "full_name": "Briana Wu",
        "password": "smoke-pw-b1",
        "is_superuser": False,
        "bio": "Full-stack developer. I work with React, TypeScript, and Node.js. Always curious about new frameworks and best practices.",
    },
    {
        "key": "user_c",
        "email": "smoke-c@cha.fan",
        "handle": "carlos_dev",
        "full_name": "Carlos Mendez",
        "password": "smoke-pw-c1",
        "is_superuser": False,
        "bio": "DevOps engineer. Kubernetes enthusiast. I run a small blog about CI/CD pipelines and container orchestration.",
    },
    {
        "key": "user_d",
        "email": "smoke-d@cha.fan",
        "handle": "diana_data",
        "full_name": "Diana Kowalski",
        "password": "smoke-pw-d1",
        "is_superuser": False,
        "bio": "Data scientist turned ML engineer. I work on NLP models and love discussing transformer architectures and fine-tuning strategies.",
    },
    {
        "key": "user_e",
        "email": "smoke-e@cha.fan",
        "handle": "ethan_ui",
        "full_name": "Ethan Park",
        "password": "smoke-pw-e1",
        "is_superuser": False,
        "bio": "Frontend developer and UX designer. I believe good interfaces are invisible. I contribute to open-source UI libraries.",
    },
    {
        "key": "user_f",
        "email": "smoke-f@cha.fan",
        "handle": "fatima_ops",
        "full_name": "Fatima Al-Rashid",
        "password": "smoke-pw-f1",
        "is_superuser": False,
        "bio": "Site reliability engineer at a fintech startup. I care about observability, incident management, and post-mortem culture.",
    },
    {
        "key": "user_g",
        "email": "smoke-g@cha.fan",
        "handle": "george_test",
        "full_name": "George Liu",
        "password": "smoke-pw-g1",
        "is_superuser": False,
        "bio": "QA engineer who learned to code. I write about test automation, TDD, and the challenges of testing legacy systems.",
    },
    {
        "key": "user_h",
        "email": "smoke-h@cha.fan",
        "handle": "hannah_mobile",
        "full_name": "Hannah Schmidt",
        "password": "smoke-pw-h1",
        "is_superuser": False,
        "bio": "Mobile developer focused on Flutter and React Native. I write about cross-platform development and app performance.",
    },
]


def _get_or_create_user(db, spec: dict):
    """Get existing user or create a new one from spec."""
    user = crud.user.get_by_email(db, email=spec["email"])
    if user:
        return user
    user_in = schemas.UserCreate(
        email=spec["email"],
        password=spec["password"],
        handle=StrippedNonEmptyBasicStr(spec["handle"]),
        full_name=StrippedNonEmptyStr(spec["full_name"]),
    )
    return crud.user.create(db, obj_in=user_in)


def _ensure_coins(db, user) -> None:
    """Top up coins to TARGET_COINS if needed."""
    if user.remaining_coins < TARGET_COINS:
        award_coins(db, user, TARGET_COINS - user.remaining_coins, reason="smoke seed")


def build_users(db) -> dict:
    """Create all users. Returns a mapping from key to User model."""
    result = {}
    for spec in USERS:
        user = _get_or_create_user(db, spec)
        # personal_introduction is a karma-bearing profile field, so this
        # assignment has to be tracked like any other profile edit -- otherwise
        # a seeded database reports drift under `scripts/refresh_karmas.py` forever
        # and people learn to ignore the one signal that catches missing hooks.
        with karma.tracked(db, user):
            user.personal_introduction = spec["bio"]
        _ensure_coins(db, user)
        result[spec["key"]] = user
    db.flush()
    return result
