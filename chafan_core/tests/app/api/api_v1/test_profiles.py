from fastapi.testclient import TestClient
from sqlalchemy.orm.session import Session

from chafan_core.app import crud
from chafan_core.app.config import settings


def test_profiles(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    example_site_uuid: str,
    normal_user_id: int,
) -> None:
    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None
    crud.profile.remove_by_user_and_site(db, owner_id=normal_user_id, site_id=site.id)
    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]
    data = {"site_uuid": example_site_uuid, "user_uuid": normal_user_uuid}

    r = client.post(
        f"{settings.API_V1_STR}/users/invite",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text

    r = client.get(
        f"{settings.API_V1_STR}/profiles/members/{example_site_uuid}/{normal_user_uuid}",
        headers=normal_user_token_headers,
    )
    assert r.ok
