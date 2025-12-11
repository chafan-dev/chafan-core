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

    # Verify the site was updated by fetching it directly
    r = client.get(f"{settings.API_V1_STR}/sites/demo_{demo_name}", headers=normal_user_token_headers)
    assert r.status_code == 200, (r.status_code, r.json())
    site = r.json()
    assert site["description"] == "Demo Site 2"
    assert site["uuid"] == site_uuid
    assert site["name"] == f"Demo ({demo_name})"
    assert site["subdomain"] == f"demo_{demo_name}"
