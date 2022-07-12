import datetime

from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.common import get_redis_cli
from chafan_core.utils.base import HTTPException_


def get_site(db: Session, site_uuid: str) -> models.Site:
    site = crud.site.get_by_uuid(db, uuid=site_uuid)
    if site is None:
        raise HTTPException_(
            status_code=400,
            detail="The site doesn't exists in the system.",
        )
    return site


def check_writing_session(uuid: str) -> None:
    redis = get_redis_cli()
    key = f"chafan:writing-session:{uuid}"
    if redis.get(key) is not None:
        raise HTTPException_(
            status_code=400,
            detail="Frondend bug: repeated posting in one writing session.",
        )
    redis.set(
        key,
        "on",
        ex=datetime.timedelta(minutes=30),
    )
