from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.topic import Topic
from chafan_core.app.schemas.topic import TopicCreate, TopicUpdate
from chafan_core.utils.validators import StrippedNonEmptyStr


class CRUDTopic(CRUDBase[Topic, TopicCreate, TopicUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[Topic]:
        return db.query(Topic).filter(Topic.name == name).first()

    def create(self, db: Session, *, obj_in: TopicCreate) -> Topic:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data, uuid=self.get_unique_uuid(db))
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_category_topics(self, db: Session) -> List[Topic]:
        return db.query(Topic).filter_by(is_category=True).all()

    def get_or_create(self, db: Session, *, name: StrippedNonEmptyStr) -> Topic:
        topic = self.get_by_name(db, name=name)
        if topic is not None:
            return topic
        return self.create(db, obj_in=TopicCreate(name=name))


topic = CRUDTopic(Topic)
