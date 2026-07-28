from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.models.profile import Profile
from chafan_core.app.schemas.profile import ProfileCreate, ProfileUpdate


def get_by_user_and_site(
    db: Session, *, owner_id: int, site_id: int
) -> Optional[Profile]:
    return db.query(Profile).filter_by(owner_id=owner_id, site_id=site_id).first()


def remove_by_user_and_site(
    db: Session, *, owner_id: int, site_id: int
) -> Optional[Profile]:
    profile = get_by_user_and_site(db, owner_id=owner_id, site_id=site_id)
    if profile:
        db.delete(profile)
        db.flush()
        return profile
    return None


def create_with_owner(db: Session, *, obj_in: ProfileCreate) -> Profile:
    site = crud.site.get_by_uuid(db, uuid=obj_in.site_uuid)
    assert site is not None
    owner = crud.user.get_by_uuid(db, uuid=obj_in.owner_uuid)
    assert owner is not None
    db_obj = Profile(owner_id=owner.id, site_id=site.id)
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Profile, obj_in: Union[ProfileUpdate, Dict[str, Any]]
) -> Profile:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    for field in update_data:
        if hasattr(db_obj, field):
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.flush()
    db.refresh(db_obj)
    return db_obj
