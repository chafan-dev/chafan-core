"""Who may mint an invitation link, and what redeeming one costs and pays.

The interesting cases here are the two edges of an invitation's life: creating
a link is gated on karma, and the link is only spent once a signup has actually
produced an account -- a rejected signup must leave the quota untouched.
"""

from typing import Dict, Tuple

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud, rules
from chafan_core.app.config import settings
from chafan_core.app.schemas.user import UserCreate
from chafan_core.tests.conftest import ensure_user_has_coins
from chafan_core.tests.utils.user import user_authentication_headers
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _make_user(
    db: Session, *, client: TestClient, karma: int
) -> Tuple[int, Dict[str, str]]:
    """A fresh account with exactly `karma` karma, plus its auth headers."""
    email = random_email()
    password = random_password()
    user = crud.user.create(
        db,
        obj_in=UserCreate(
            email=email, password=password, handle=random_short_lower_string()
        ),
    )
    crud.user.update(db, db_obj=user, obj_in={"karma": karma})
    # crud flushes only; the login below runs on another session.
    db.commit()
    user_id = user.id
    headers = user_authentication_headers(client=client, email=email, password=password)
    return user_id, headers


def _remaining_quota(client: TestClient, uuid: str) -> int:
    r = client.get(f"{settings.API_V1_STR}/invitation-links/{uuid}")
    assert 200 <= r.status_code < 300, r.text
    return r.json()["remaining_quota"]


def _open_account(client: TestClient, uuid: str, email: str) -> int:
    """Attempt a signup with `uuid`; return the status code."""
    return client.post(
        f"{settings.API_V1_STR}/open-account",
        json={
            "email": email,
            "password": random_password().get_secret_value(),
            "handle": random_short_lower_string(),
            "code": "magic_dev",
            "invitation_link_uuid": uuid,
        },
    ).status_code


def test_create_invitation_link_rejected_below_karma_gate(
    client: TestClient, db: Session
) -> None:
    _, headers = _make_user(db, client=client, karma=rules.MIN_KARMA_INVITE_USER - 1)
    r = client.post(
        f"{settings.API_V1_STR}/invitation-links/", headers=headers, json={}
    )
    assert r.status_code == 403, r.text


def test_create_invitation_link_allowed_at_karma_gate(
    client: TestClient, db: Session
) -> None:
    _, headers = _make_user(db, client=client, karma=rules.MIN_KARMA_INVITE_USER)
    r = client.post(
        f"{settings.API_V1_STR}/invitation-links/", headers=headers, json={}
    )
    assert 200 <= r.status_code < 300, r.text
    assert r.json()["remaining_quota"] == rules.INVITE_LINK_QUOTA
    assert r.json()["valid"] is True


def test_rejected_signup_does_not_consume_quota(
    client: TestClient, db: Session
) -> None:
    _, headers = _make_user(db, client=client, karma=rules.MIN_KARMA_INVITE_USER)
    uuid = client.post(
        f"{settings.API_V1_STR}/invitation-links/", headers=headers, json={}
    ).json()["uuid"]
    before = _remaining_quota(client, uuid)

    # An email already in use: rejected after the link has been checked but
    # before any account exists.
    taken_id, _ = _make_user(db, client=client, karma=0)
    db.expire_all()
    taken_email = crud.user.get(db, id=taken_id).email
    assert _open_account(client, uuid, taken_email) == 401

    assert _remaining_quota(client, uuid) == before


def test_successful_signup_consumes_quota_and_pays_inviter(
    client: TestClient, db: Session
) -> None:
    inviter_id, headers = _make_user(
        db, client=client, karma=rules.MIN_KARMA_INVITE_USER
    )
    # The admin funds the reward, so it has to be able to afford it.
    ensure_user_has_coins(db, crud.user.get_superuser(db).id, coins=100)

    uuid = client.post(
        f"{settings.API_V1_STR}/invitation-links/", headers=headers, json={}
    ).json()["uuid"]
    before = _remaining_quota(client, uuid)

    db.expire_all()
    inviter = crud.user.get(db, id=inviter_id)
    coins_before = inviter.remaining_coins
    invitations_before = inviter.sent_new_user_invitataions

    new_email = random_email()
    assert 200 <= _open_account(client, uuid, new_email) < 300

    assert _remaining_quota(client, uuid) == before - 1

    db.expire_all()
    inviter = crud.user.get(db, id=inviter_id)
    assert inviter.remaining_coins == coins_before + rules.INVITE_NEW_USER_REWARD
    assert inviter.sent_new_user_invitataions == invitations_before + 1

    invited = crud.user.get_by_email(db, email=new_email)
    assert invited is not None
    assert invited.remaining_coins == rules.INITIAL_USER_COINS


def test_daily_link_signup_pays_nobody(client: TestClient, db: Session) -> None:
    """The daily link's inviter is the admin, who funds the reward themselves."""
    uuid = client.get(f"{settings.API_V1_STR}/invitation-links/daily").json()["uuid"]

    db.expire_all()
    superuser = crud.user.get_superuser(db)
    superuser_id = superuser.id
    coins_before = superuser.remaining_coins
    invitations_before = superuser.sent_new_user_invitataions

    assert 200 <= _open_account(client, uuid, random_email()) < 300

    db.expire_all()
    superuser = crud.user.get(db, id=superuser_id)
    assert superuser.remaining_coins == coins_before
    assert superuser.sent_new_user_invitataions == invitations_before
