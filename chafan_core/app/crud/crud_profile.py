from typing import Optional

from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.profile import Profile
from chafan_core.app.schemas.profile import ProfileCreate, ProfileUpdate


class CRUDProfile(CRUDBase[Profile, ProfileCreate, ProfileUpdate]):
    def get_by_user_and_site(
        self, db: Session, *, owner_id: int, site_id: int
    ) -> Optional[Profile]:
        return db.query(Profile).filter_by(owner_id=owner_id, site_id=site_id).first()

    def remove_by_user_and_site(
        self, db: Session, *, owner_id: int, site_id: int
    ) -> Optional[Profile]:
        profile = self.get_by_user_and_site(db, owner_id=owner_id, site_id=site_id)
        if profile:
            db.delete(profile)
            db.commit()
            return profile
        return None

    def create_with_owner(self, db: Session, *, obj_in: ProfileCreate) -> Profile:
        site = crud.site.get_by_uuid(db, uuid=obj_in.site_uuid)
        assert site is not None
        owner = crud.user.get_by_uuid(db, uuid=obj_in.owner_uuid)
        assert owner is not None
        db_obj = Profile(owner_id=owner.id, site_id=site.id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


profile = CRUDProfile(Profile)
