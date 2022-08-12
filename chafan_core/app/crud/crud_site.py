import datetime
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.site import Site
from chafan_core.app.schemas.site import SiteCreate, SiteUpdate
from chafan_core.app.search import do_search


class CRUDSite(CRUDBase[Site, SiteCreate, SiteUpdate]):
    def get_by_subdomain(self, db: Session, *, subdomain: str) -> Optional[Site]:
        return db.query(Site).filter(Site.subdomain == subdomain).first()

    def get_by_id(self, db: Session, *, id: int) -> Optional[Site]:
        return db.query(Site).filter(Site.id == id).first()

    def get_by_name(self, db: Session, *, name: str) -> Optional[Site]:
        return db.query(Site).filter(Site.name == name).first()

    def get_multi_questions(
        self, db: Session, *, db_obj: Site, skip: int, limit: int
    ) -> List[models.Question]:
        return db_obj.questions[skip : (skip + limit)]

    def get_multi_submissions(
        self, db: Session, *, db_obj: Site, skip: int, limit: int
    ) -> List[models.Submission]:
        return db_obj.submissions[skip : (skip + limit)]

    def get_all_public_readable(self, db: Session) -> List[models.Site]:
        return db.query(models.Site).filter_by(public_readable=True).all()

    def get_all(self, db: Session) -> List[models.Site]:
        return db.query(models.Site).all()

    def search(self, db: Session, *, fragment: str) -> List[Site]:
        ids = do_search("site", query=fragment)
        if not ids:
            return []
        ret = []
        for id in ids:
            site = self.get(db, id=id)
            if site:
                ret.append(site)
        return ret

    def create_with_permission_type(
        self,
        db: Session,
        *,
        obj_in: SiteCreate,
        moderator: models.User,
        category_topic_id: Optional[int]
    ) -> Site:
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        obj_in_data = jsonable_encoder(obj_in)
        obj_in_data["moderator_id"] = moderator.id
        if obj_in.permission_type == "public":
            obj_in_data["public_readable"] = True
            obj_in_data["public_writable_question"] = True
            obj_in_data["public_writable_submission"] = True
            obj_in_data["public_writable_answer"] = True
            obj_in_data["public_writable_comment"] = True
        # TODO: turn on the community service flags after implementation
        if "category_topic_uuid" in obj_in_data:
            del obj_in_data["category_topic_uuid"]
        if category_topic_id:
            obj_in_data["category_topic_id"] = category_topic_id
        del obj_in_data["permission_type"]
        db_obj = self.model(
            **obj_in_data, uuid=self.get_unique_uuid(db), created_at=utc_now
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_all_with_category_topic_ids(
        self, db: Session, category_topic_id: int
    ) -> List[Site]:
        return (
            db.query(models.Site).filter_by(category_topic_id=category_topic_id).all()
        )


site = CRUDSite(Site)
