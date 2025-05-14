import uuid
import re
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, select, DateTime
from sqlalchemy.orm import joinedload, selectinload, Load
from sqlalchemy.orm.interfaces import MapperOption
from sqlalchemy.ext.asyncio import AsyncSession, AsyncAttrs
from sqlalchemy.inspection import inspect

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from typing import Any, Optional, Union, Self, AsyncGenerator


def to_snake_case(name: str) -> str:
    # Find all positions where an uppercase letter is preceded by a lowercase letter or followed by a lowercase letter.
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return name


Base = declarative_base()


class BaseTable(Base, AsyncAttrs):
    __abstract__ = True

    id = Column(String(length=128), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__tablename__ = to_snake_case(cls.__name__)
        cls.__tablename__ = cls.__tablename__.removesuffix("_table")


class FromDBModel(BaseModel):
    __ormclass__ = None
    id: SkipJsonSchema[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: SkipJsonSchema[datetime] = Field(default=datetime.now(timezone.utc))
    updated_at: SkipJsonSchema[datetime] = Field(default=datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
        

    @staticmethod
    def _build_load_options(
        orm_cls: type,
        max_depth: int,
        *,
        _current_depth: int = 0,
        _seen: set[type] | None = None,
    ) -> list:
        if _current_depth >= max_depth:
            return []
        seen = set() if _seen is None else _seen
        # don't re‑visit the same class
        if orm_cls in seen:
            return []
        seen.add(orm_cls)

        opts: list = []
        mapper = inspect(orm_cls)
        for rel in mapper.relationships:
            loader = selectinload(getattr(orm_cls, rel.key))
            # recurse, passing along our growing “seen” set
            nested = FromDBModel._build_load_options(
                rel.mapper.class_,
                max_depth,
                _current_depth=_current_depth + 1,
                _seen=seen,
            )
            if nested:
                loader = loader.options(*nested)
            opts.append(loader)

        return opts

    @classmethod
    async def from_id(cls, session: AsyncSession, id_: str) -> AsyncGenerator[Self]:
        load_opts = cls._build_load_options(cls.__ormclass__, 2)
        stmt = (
            select(cls.__ormclass__)
            .options(*load_opts)
            .where(cls.__ormclass__.id == id_)
        )
        instance = (await session.execute(stmt)).scalar_one_or_none()
        return cls.model_validate(instance)


    def check_orm_fields(self, field_name) -> bool:
        mapper = inspect(self.__ormclass__)

        # List all column attributes
        columns = [column.key for column in mapper.columns]
        relationship_names = [relation.key for relation in mapper.relationships]

        return field_name in columns or field_name in relationship_names

    def to_orm(
        self,
        parent_id: Optional[str] = None,
        parent_field_name: Optional[str] = None,
    ) -> Any:
        """
        Recursively converts the Pydantic model and its nested objects to a SQLAlchemy model.

        Args:
            parent_id (Optional[str]): The ID of the parent object, if available.
            parent_field_name (Optional[str]): The field name to use for the foreign key reference in child objects.

        Returns:
            An instance of the SQLAlchemy model defined in the __ormclass__ attribute of the Pydantic model.
        """
        if not self.__ormclass__:
            raise ValueError(f"ORM class not defined for {self.__class__.__name__}")

        orm_fields = {}
        for field_name in self.model_fields:
            if not self.check_orm_fields(field_name=field_name):
                continue
            value = getattr(self, field_name)

            if hasattr(self.__ormclass__, field_name):
                if isinstance(value, FromDBModel):
                    # Pass the current object's id to its child as the parent_id
                    orm_fields[field_name] = value.to_orm(
                        parent_id=self.id,
                        parent_field_name=f"{self.__class__.__name__.lower()}_id",
                    )
                elif isinstance(value, list):
                    if len(value) > 0:
                        if isinstance(value[0], FromDBModel):
                            # Handle lists of nested Pydantic models, passing parent_id to each item
                            orm_fields[field_name] = [
                                item.to_orm(
                                    parent_id=self.id,
                                    parent_field_name=f"{self.__class__.__name__.lower()}_id",
                                )
                                for item in value
                            ]
                    else:
                        orm_fields[field_name] = []
                else:
                    if value:
                        orm_fields[field_name] = value

        # If a parent_id and field name are provided, add them to the ORM fields
        if parent_id and parent_field_name and hasattr(self.__ormclass__, parent_field_name):
            orm_fields[parent_field_name] = parent_id

        return self.__ormclass__(**orm_fields)
