# flake8: noqa

from typing import Any, List, Optional

from sqlalchemy.ext.declarative import as_declarative, declared_attr


@as_declarative()
class Base:
    id: Any
    __name__: str
    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    printed_attrs: Optional[List[str]] = None

    def __str__(self) -> str:
        if self.printed_attrs:
            attrs = ", ".join(f"{a}={getattr(self, a)}" for a in self.printed_attrs)
            return self.__class__.__name__ + "(" + attrs + ")"
        elif hasattr(self, "id"):
            return self.__class__.__name__ + f"(id={self.id})"
        return self.__str__()
