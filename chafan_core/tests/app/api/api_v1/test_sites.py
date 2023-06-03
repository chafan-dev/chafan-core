from fastapi.testclient import TestClient

from chafan_core.app.config import settings
from chafan_core.tests.utils.utils import random_short_lower_string


def test_sites(
    client: TestClient,
    moderator_user_token_headers: dict,
    superuser_token_headers: dict,
    normal_user_token_headers: dict,
    moderator_user_uuid: str,
) -> None:
    r = client.get(f"{settings.API_V1_STR}/sites", headers=normal_user_token_headers)
    r.raise_for_status()
    existing_sites = r.json()

    demo_name = random_short_lower_string()

    data = {
        "name": f"Demo ({demo_name})",
        "description": "Demo Site",
        "subdomain": f"demo_{demo_name}",
        "permission_type": "private",
    }

    r = client.post(f"{settings.API_V1_STR}/sites/", json=data)
    assert r.status_code == 401

    r = client.post(
        f"{settings.API_V1_STR}/sites/", headers=superuser_token_headers, json=data
    )
    assert 200 <= r.status_code < 300, r.text
    assert r.json()["created_site"]["name"] == f"Demo ({demo_name})"
    site_uuid = r.json()["created_site"]["uuid"]

    data = {
        "description": "Demo Site 2",
        "moderator_uuid": moderator_user_uuid,
    }

    r = client.put(f"{settings.API_V1_STR}/sites/{site_uuid}", json=data)
    assert r.status_code == 405, r.json()

    r = client.put(
        f"{settings.API_V1_STR}/sites/{site_uuid}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 405

    r = client.put(
        f"{settings.API_V1_STR}/sites/{site_uuid}/config",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300, r.text
    assert r.json()["description"] == "Demo Site 2"

    r = client.get(f"{settings.API_V1_STR}/sites", headers=normal_user_token_headers)
    assert r.status_code == 200, (r.status_code, r.json())
    sites = r.json()
    assert sites == existing_sites + [
        {
            "description": "Demo Site 2",
            "uuid": site_uuid,
            "name": f"Demo ({demo_name})",
            "subdomain": f"demo_{demo_name}",
            "public_readable": False,
            "public_writable_question": False,
            "public_writable_submission": False,
            "public_writable_answer": False,
            "public_writable_comment": False,
            "create_question_coin_deduction": 2,
            "moderator": {
                "uuid": moderator_user_uuid,
                "avatar_url": None,
                "full_name": None,
                "follows": None,
                "handle": "mod",
                "karma": 0,
                "personal_introduction": None,
                "social_annotations": {"follow_follows": None},
            },
            "addable_member": True,
            "topics": [],
            "permission_type": "private",
            "auto_approval": True,
            "min_karma_for_application": None,
            "email_domain_suffix_for_application": None,
            "questions_count": 0,
            "submissions_count": 0,
            "members_count": 1,
            "category_topic": None,
        }
    ]
