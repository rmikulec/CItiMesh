import uuid
import re

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String
from sqlalchemy.inspection import inspect

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from typing import Any, Optional


def to_snake_case(name: str) -> str:
    # Find all positions where an uppercase letter is preceded by a lowercase letter or followed by a lowercase letter.
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return name


Base = declarative_base()


class BaseTable(Base):
    __abstract__ = True

    id = Column(String(length=128), primary_key=True, default=lambda: str(uuid.uuid4()))

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__tablename__ = to_snake_case(cls.__name__)
        cls.__tablename__ = cls.__tablename__.removesuffix("_table")


class FromDBModel(BaseModel):
    __ormclass__ = None
    id: SkipJsonSchema[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    model_config = ConfigDict(from_attributes=True)

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
