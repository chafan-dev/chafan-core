from sqlalchemy.orm import Session

from chafan_core.app import crud, schemas
from chafan_core.app.config import settings
from chafan_core.utils.validators import StrippedNonEmptyBasicStr  # noqa: F401
from chafan_core.utils.validators import StrippedNonEmptyStr

# make sure all SQL Alchemy models are imported (app.db.base) before initializing DB
# otherwise, SQL Alchemy might fail to initialize relationships properly
# for more details: https://github.com/tiangolo/full-stack-fastapi-postgresql/issues/28


def init_db(db: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next line
    # Base.metadata.create_all(bind=engine)
    assert settings.FIRST_SUPERUSER is not None
    assert settings.FIRST_SUPERUSER_PASSWORD is not None
    user = crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = schemas.UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            full_name=StrippedNonEmptyStr("Admin"),
            is_superuser=True,
            handle=StrippedNonEmptyBasicStr("super"),
        )
        user = crud.user.create(db, obj_in=user_in)  # noqa: F841
