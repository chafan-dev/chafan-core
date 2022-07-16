from fastapi.testclient import TestClient

from chafan_core.utils.base import get_uuid
from chafan_core.app.config import settings


def test_answers(
    client: TestClient,
    normal_user_token_headers: dict,
    normal_user_authored_question_uuid: str,
) -> None:
    data = {
        "question_uuid": normal_user_authored_question_uuid,
        "content": {
            "source": "test answer",
            "rendered_text": "test answer",
            "editor": "markdown",
        },
        "is_published": True,
        "is_autosaved": False,
        "visibility": "anyone",
        "writing_session_uuid": get_uuid(),
    }

    r = client.post(f"{settings.API_V1_STR}/answers/", json=data,)
    assert r.status_code == 401

    r = client.post(
        f"{settings.API_V1_STR}/answers/", headers=normal_user_token_headers, json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    assert "author" in r.json(), r.json()
    normal_user_uuid = client.get(
        f"{settings.API_V1_STR}/me", headers=normal_user_token_headers
    ).json()["uuid"]
    assert r.json()["author"]["uuid"] == normal_user_uuid
