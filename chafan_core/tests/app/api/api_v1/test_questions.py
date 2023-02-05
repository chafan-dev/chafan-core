from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.tests.utils.utils import random_lower_string


def test_questions(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    normal_user_id: int,
    example_site_uuid: str,
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/questions/", json={"site_uuid": example_site_uuid}
    )
    assert r.status_code == 401

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid + "0",
            "title": "example title",
            "description": "",
        },
    )
    assert r.status_code == 400, r.json()

    data = {
        "site_uuid": example_site_uuid,
        "title": "test question",
        "description": random_lower_string(),
    }

    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    crud.profile.remove_by_user_and_site(db, owner_id=normal_user_id, site_id=site.id)

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 400

    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]

    profile = crud.profile.get_by_user_and_site(
        db, owner_id=normal_user_id, site_id=site.id
    )
    if not profile:
        r = client.post(
            f"{settings.API_V1_STR}/users/invite",
            headers=superuser_token_headers,
            json={"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid},
        )
        r.raise_for_status()

    r = client.post(
        f"{settings.API_V1_STR}/questions/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    assert "author" in r.json(), r.json()
    assert r.json()["author"]["uuid"] == normal_user_uuid
    question_uuid = r.json()["uuid"]

    r = client.get(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200

    r = client.put(
        f"{settings.API_V1_STR}/questions/{question_uuid}",
        headers=normal_user_token_headers,
        json={"site_uuid": example_site_uuid, "description": "new intro"},
    )
    assert r.status_code == 200
