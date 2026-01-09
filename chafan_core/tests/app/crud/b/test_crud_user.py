import asyncio
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.user import UserCreate, UserUpdate
from chafan_core.app.security import verify_password
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def test_create_user(db: Session) -> None:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        email=email, password=password, handle=random_short_lower_string()
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    assert user.email == email
    assert hasattr(user, "hashed_password")


def test_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        email=email, password=password, handle=random_short_lower_string()
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    authenticated_user = crud.user.authenticate(db, email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


def test_not_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_password()
    user = crud.user.authenticate(db, email=email, password=password)
    assert user is None


def test_check_if_user_is_active(db: Session) -> None:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        email=email, password=password, handle=random_short_lower_string()
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    is_active = crud.user.is_active(user)
    assert is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        handle=random_short_lower_string(),
        email=email,
        password=password,
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    is_active = crud.user.is_active(user)
    assert is_active


def test_check_if_user_is_superuser(db: Session) -> None:
    email = random_email()
    password = random_password()
    user_in = UserCreate(
        handle=random_short_lower_string(),
        email=email,
        password=password,
        is_superuser=True,
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    is_superuser = crud.user.is_superuser(user)
    assert is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    username = random_email()
    password = random_password()
    user_in = UserCreate(
        handle=random_short_lower_string(), email=username, password=password
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    is_superuser = crud.user.is_superuser(user)
    assert is_superuser is False


def test_get_user(db: Session) -> None:
    password = random_password()
    username = random_email()
    user_in = UserCreate(
        handle=random_short_lower_string(),
        email=username,
        password=password,
        is_superuser=True,
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    user_2 = crud.user.get(db, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    password = random_password()
    email = random_email()
    user_in = UserCreate(
        email=email,
        handle=random_short_lower_string(),
        password=password,
        is_superuser=True,
    )
    user = asyncio.run(crud.user.create(db, obj_in=user_in))
    new_password = random_password()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    crud.user.update(db, db_obj=user, obj_in=user_in_update)
    user_2 = crud.user.get(db, id=user.id)
    assert user_2
    assert user.email == user_2.email
    assert verify_password(new_password, user_2.hashed_password)
