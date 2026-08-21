"""The bot link flow: generate a code, redeem it, and revoke what it minted."""

from typing import Dict

import pytest
from fastapi.testclient import TestClient
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.services import bot_links as bot_links_service
from chafan_core.app.services import tokens as tokens_service

BOT_SECRET = "test-bot-secret-value"


@pytest.fixture(autouse=True)
def configured_bot(monkeypatch):
    monkeypatch.setattr(
        settings, "BOT_SECRETS", {"discord": SecretStr(BOT_SECRET)}, raising=False
    )


def _generate_code(client: TestClient, headers: Dict[str, str]) -> str:
    r = client.post(f"{settings.API_V1_STR}/me/bot-link-codes/", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _claim(client: TestClient, code: str, secret: str = BOT_SECRET):
    return client.post(
        f"{settings.API_V1_STR}/bot/claim-link/",
        json={"secret": secret, "code": code},
    )


def test_a_code_becomes_a_token_for_the_user_who_generated_it(
    client: TestClient, normal_user_token_headers: dict, normal_user_id: int
) -> None:
    code = _generate_code(client, normal_user_token_headers)
    r = _claim(client, code)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    # The token acts as that user and nobody else.
    me = client.get(
        f"{settings.API_V1_STR}/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["id"] == normal_user_id


def test_the_code_is_shown_with_a_dash_and_accepted_without_one(
    client: TestClient, normal_user_token_headers: dict
) -> None:
    code = _generate_code(client, normal_user_token_headers)
    assert "-" in code
    # Whichever way it comes back from a person retyping it.
    assert _claim(client, code.replace("-", "")).status_code == 200


def test_a_code_is_single_use(
    client: TestClient, normal_user_token_headers: dict
) -> None:
    # Otherwise a code seen over someone's shoulder stays good for its whole TTL.
    code = _generate_code(client, normal_user_token_headers)
    assert _claim(client, code).status_code == 200
    assert _claim(client, code).status_code == 400


def test_a_wrong_secret_claims_nothing(
    client: TestClient, normal_user_token_headers: dict
) -> None:
    code = _generate_code(client, normal_user_token_headers)
    assert _claim(client, code, secret="not-the-secret").status_code == 400
    # And the code survives, so a guesser cannot burn other people's codes.
    assert _claim(client, code).status_code == 200


def test_an_unknown_code_is_refused(client: TestClient) -> None:
    assert _claim(client, "AAAA-AAAA").status_code == 400


def test_generating_a_code_requires_being_logged_in(client: TestClient) -> None:
    # The whole direction of the flow rests on this: the code can only appear
    # on the screen of someone already authenticated as the account.
    r = client.post(f"{settings.API_V1_STR}/me/bot-link-codes/")
    assert r.status_code in (401, 403)


def test_no_secret_configured_means_nothing_can_be_claimed(
    client: TestClient, normal_user_token_headers: dict, monkeypatch
) -> None:
    code = _generate_code(client, normal_user_token_headers)
    monkeypatch.setattr(settings, "BOT_SECRETS", {}, raising=False)
    assert _claim(client, code).status_code == 400


def test_revoke_refuses_the_bot_token_and_keeps_the_website_session(
    client: TestClient, normal_user_token_headers: dict
) -> None:
    code = _generate_code(client, normal_user_token_headers)
    bot_token = _claim(client, code).json()["access_token"]
    bot_headers = {"Authorization": f"Bearer {bot_token}"}
    assert (
        client.get(f"{settings.API_V1_STR}/me", headers=bot_headers).status_code == 200
    )

    r = client.post(f"{settings.API_V1_STR}/bot/revoke/", headers=bot_headers)
    assert r.status_code == 200, r.text

    # The bot token is dead...
    assert (
        client.get(f"{settings.API_V1_STR}/me", headers=bot_headers).status_code == 403
    )
    # ...and the browser session it was minted alongside is not.
    assert (
        client.get(
            f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
        ).status_code
        == 200
    )


def test_a_new_link_works_after_a_revoke(
    client: TestClient, normal_user_token_headers: dict
) -> None:
    # Revocation must not brick the account for future links: the new token is
    # stamped with the bumped version and so is not behind it.
    first = _claim(client, _generate_code(client, normal_user_token_headers))
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    client.post(f"{settings.API_V1_STR}/bot/revoke/", headers=first_headers)

    second = _claim(client, _generate_code(client, normal_user_token_headers))
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    assert (
        client.get(f"{settings.API_V1_STR}/me", headers=second_headers).status_code
        == 200
    )


def test_revoking_all_tokens_also_ends_the_website_session(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_id: int,
) -> None:
    # The other counter, the one a "log out everywhere" control would bump.
    code = _generate_code(client, normal_user_token_headers)
    bot_headers = {
        "Authorization": f"Bearer {_claim(client, code).json()['access_token']}"
    }

    user = crud.user.get(db, id=normal_user_id)
    tokens_service.revoke_all_tokens(db, user=user)
    db.commit()
    try:
        assert (
            client.get(f"{settings.API_V1_STR}/me", headers=bot_headers).status_code
            == 403
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
            ).status_code
            == 403
        )
    finally:
        # Other modules share this user; put it back the way it was found.
        user.token_version = 0
        db.add(user)
        db.commit()
        tokens_service._forget(user.id)


def test_normalize_and_format_round_trip() -> None:
    assert bot_links_service.normalize_code(" k4f2-9qtx ") == "K4F29QTX"
    assert bot_links_service.format_code("K4F29QTX") == "K4F2-9QTX"
