from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from chafan_core.utils.base import get_uuid
from chafan_core.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    def get_by_uuid(self, db: Session, *, uuid: str) -> Optional[ModelType]:
        return db.query(self.model).filter_by(uuid=uuid).first()

    def get_unique_uuid(self, db: Session) -> str:
        while True:
            uuid = get_uuid()
            if self.get_by_uuid(db, uuid=uuid) is None:
                return uuid

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_ilike(
        self, db: Session, *, fragment: str, column: Any, limit: int = 5
    ) -> List[ModelType]:
        same_ones = (
            db.query(self.model)
            .filter(column.ilike(f"{fragment}"))
            .order_by(desc(func.length(column)))
            .limit(limit)
            .all()
        )
        similar_ones = (
            db.query(self.model)
            .filter(column.ilike(f"%{fragment}%"))
            .order_by(desc(func.length(column)))
            .limit(limit)
            .all()
        )
        return same_ones + [s for s in similar_ones if s not in same_ones]

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def get_all(self, db: Session) -> List[ModelType]:
        return db.query(self.model).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> Optional[ModelType]:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj
