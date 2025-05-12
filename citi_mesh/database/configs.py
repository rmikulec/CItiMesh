from datetime import datetime
from typing import Optional, List
from enum import Enum
from datetime import datetime

from pydantic import Field, model_validator, create_model
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from citi_mesh.database.base import BaseTable, FromDBModel


# --------------------------------------------------------------------
# SQLAlchemy Models
# --------------------------------------------------------------------
class TenantTable(BaseTable):
    name = Column(String(length=32), unique=True, index=True)
    display_name = Column(String(length=32), unique=True)
    registered_number = Column(String(length=17), unique=True)
    subdomain = Column(String(length=16), unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    providers = relationship(
        "ProviderTable", back_populates="tenant", cascade="all, delete-orphan"
    )
    resource_types = relationship(
        "ResourceTypeTable", back_populates="tenant", cascade="all, delete-orphan"
    )
    resources = relationship(
        "ResourceTable", back_populates="tenant", cascade="all, delete-orphan"
    )


class AnalyticConfig(BaseTable):
    name = Column(String(length=32), unique=True)
    display_name = Column(String(length=32), unique=True)
    description = Column(Text)
    value_type = Column(String(length=16))
    