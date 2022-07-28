from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings

malformed_request_stdout = """Validation error:
request.url: http://testserver/api/v1/comments/
request.method: POST
exc: 1 validation error for Request
body -> content -> editor
  field required (type=value_error.missing)
exc.body: {'site_uuid': '%s', 'question_uuid': '%s', 'content': {'source': 'test comment', 'rendered_text': 'test comment'}}
"""


def test_comments(
    client: TestClient,
    db: Session,
    capfd: Any,
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

    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        json=data,
    )
    assert r.status_code == 401

    # Test malformed request
    r = client.post(
        f"{settings.API_V1_STR}/comments/",
        headers=normal_user_token_headers,
        json={
            "site_uuid": example_site_uuid,
            "question_uuid": normal_user_authored_question_uuid,
            "content": {
                "source": "test comment",
                "rendered_text": "test comment",
                # Missing editor field
            },
        },
    )
    assert r.status_code == 422, r.text
    out, _ = capfd.readouterr()
    assert out == malformed_request_stdout % (
        example_site_uuid,
        normal_user_authored_question_uuid,
    ), out

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
