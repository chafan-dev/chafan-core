# flake8: noqa

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase  # type: ignore


class Base(DeclarativeBase):
    __allow_unmapped__ = True

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
