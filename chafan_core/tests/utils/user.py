from typing import Dict

from fastapi.testclient import TestClient
from pydantic.types import SecretStr
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.config import settings
from chafan_core.app.models.user import User
from chafan_core.app.schemas.user import UserCreate, UserUpdate
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)
from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    StrippedNonEmptyBasicStr,
)


def user_authentication_headers(
    *, client: TestClient, email: str, password: SecretStr
) -> Dict[str, str]:
    data = {"username": email, "password": password.get_secret_value()}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


async def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        email=email, password=password, handle=random_short_lower_string()
    )
    user = await crud.user.create(db=db, obj_in=user_in)
    return user


async def authentication_token_from_email(
    *, client: TestClient, email: CaseInsensitiveEmailStr, db: Session
) -> Dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_password()
    user = crud.user.get_by_email(db, email=email)
    if not user:
        user_in_create = UserCreate(
            email=email,
            password=password,
            handle=StrippedNonEmptyBasicStr(email.split("@")[0]),
        )
        user = await crud.user.create(db, obj_in=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        user = crud.user.update(db, db_obj=user, obj_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)
