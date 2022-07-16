from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from chafan_core.app.config import settings


def test_comments(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
    example_site_uuid: str,
) -> None:
    data = {
        "site_uuid": example_site_uuid,
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "test comment",
            "rendered_text": "test comment",
            "editor": "wysiwyg",
        },
    }

    r = client.post(f"{settings.API_V1_STR}/comments/", json=data,)
    assert r.status_code == 401

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    assert "author" in r.json(), r.json()
    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]
    assert r.json()["author"]["uuid"] == normal_user_uuid
    comment_id = r.json()["uuid"]

    site = crud.site.get_by_uuid(db, uuid=example_site_uuid)
    assert site is not None

    r = client.get(
        f"{settings.API_V1_STR}/comments/{comment_id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200

    r = client.put(
        f"{settings.API_V1_STR}/comments/{comment_id}",
        headers=normal_user_token_headers,
        json={"body": "new comment"},
    )
    assert r.status_code == 200
