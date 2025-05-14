import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Load, declarative_base, selectinload

from citi_mesh.database._exceptions import InstanceNotFound


def _to_snake_case(name: str) -> str:
    """
    Helper function to change any given name to snake case
    I.E
        SnakeCase -> snake_case
    """
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return name


# Declare the database's Base
Base = declarative_base()


class SQLTable(Base, AsyncAttrs):
    """
    Abstract class to be used to create tables in the database.

    Any SQLAlchemy class that extends this will be automatically added to the databse

    Class also does the following:
        - Adds  'id', 'created_at', and 'updated_at' columns
        - Changes the table name to be snakecase
    """

    __abstract__ = True

    id = Column(String(length=128), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__tablename__ = _to_snake_case(cls.__name__)
        cls.__tablename__ = cls.__tablename__.removesuffix("_table")


class SQLModel(BaseModel):
    """
    A Pydantic model that serves as an intermediary for FastAPI and any CRUD operations

    When extending this class, the '__ormclass__' field must be populated with its respected
    SQLTable class. This is what allows this class to automatically sync with real data in the
    database

    Class Methods:
        - async from_id(session: AsyncSession, id_: str): creates and returns an instance of the
            class given its corresponding ID in the database.
        - async sync_to_db(session: AsyncSession): Syncs any updated data in the class with its
            respective table (and subtables) in the db
    """

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
    ) -> list[Load]:
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
            nested = SQLModel._build_load_options(
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
    async def from_id(cls, session: AsyncSession, id_: str) -> Self:
        """
        Creates an instance of the class given a Database ID. This function recursively queires
        for all subclasses.

        args:
            session(AsyncSession): An Async SQLAlchemy Session object
            id_(str): The id of the entry in the database
        """
        load_opts = cls._build_load_options(cls.__ormclass__, 2)
        stmt = select(cls.__ormclass__).options(*load_opts).where(cls.__ormclass__.id == id_)
        instance = (await session.execute(stmt)).scalar_one_or_none()

        if not instance:
            raise InstanceNotFound(id_=id_, model=cls.__name__)

        return cls.model_validate(instance)

    def _check_orm_fields(self, field_name) -> bool:
        """
        Private to check a 'field_name' in the orm model. This includes columns and relationships.
        Returns 'True' if the field exists in the orm model and 'False' if it does not.
        """
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
            parent_field_name (Optional[str]): The field name to use for the foreign key reference
                in child objects.

        Returns:
            An instance of the SQLAlchemy model defined in the __ormclass__ attribute of the
                Pydantic model.
        """
        if not self.__ormclass__:
            raise ValueError(f"ORM class not defined for {self.__class__.__name__}")

        orm_fields = {}
        for field_name in self.model_fields:
            if not self._check_orm_fields(field_name=field_name):
                continue
            value = getattr(self, field_name)

            if hasattr(self.__ormclass__, field_name):
                if isinstance(value, SQLModel):
                    # Pass the current object's id to its child as the parent_id
                    orm_fields[field_name] = value.to_orm(
                        parent_id=self.id,
                        parent_field_name=f"{self.__class__.__name__.lower()}_id",
                    )
                elif isinstance(value, list):
                    if len(value) > 0:
                        if isinstance(value[0], SQLModel):
                            # Handle lists of nested Pydantic models, passing parent_id
                            # to each item
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

    async def upsert(self, session: AsyncSession):
        """
        Upserts data into the database.

        args:
            - session(AsyncSession): An Async SQLAlchemy Session object

        """
        instance = self.to_orm()
        await session.merge(instance)
        await session.commit()
        await session.flush()
