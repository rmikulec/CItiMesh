from datetime import datetime
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, DynamicMapped
from citi_mesh.database.base import BaseTable

class TenantTable(BaseTable):
    name = Column(String(length=32), unique=True, index=True)
    display_name = Column(String(length=32), unique=True)
    registered_number = Column(String(length=17), unique=True)
    subdomain = Column(String(length=16), unique=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    providers = relationship(
        "ProviderTable", back_populates=None, cascade="all, delete-orphan"
    )


class ResourceTypeTable(BaseTable):
    provider_id = Column(String(length=128), ForeignKey("provider.id"))
    name = Column(String(length=64))
    display_name = Column(String)  # formerly "name_pretty"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_resource_type_provider_id_name", "provider_id", "name", unique=False),
    )

    # Many-to-many link back to resources
    resources = relationship(
        "ResourceTable", secondary="resource_type_link", back_populates="resource_types"
    )


class ResourceTable(BaseTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    provider_id = Column(String(length=128), ForeignKey("provider.id"), nullable=True)
    name = Column(String(length=128))
    description = Column(Text)
    phone_number = Column(String)
    website = Column(String)
    address_id = Column(String(length=128), ForeignKey("address.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    address = relationship("AddressTable", back_populates="resources")

    resource_types = relationship(
        "ResourceTypeTable", secondary="resource_type_link", back_populates="resources"
    )


class ResourceTypeLinkTable(BaseTable):
    # Composite PK of (resource_id, resource_type_id)
    resource_id = Column(String(length=128), ForeignKey("resource.id"), primary_key=True)
    resource_type_id = Column(String(length=128), ForeignKey("resource_type.id"), primary_key=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AddressTable(BaseTable):
    street = Column(String(128))
    street2 = Column(String(128), nullable=True)
    city = Column(String(64))
    state = Column(String(16))  # e.g. US state abbreviations
    zip_code = Column(String(10))
    google_place_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resources = relationship("ResourceTable", back_populates="address")


class ProviderTable(BaseTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    name = Column(String(length=64))
    display_name = Column(String(length=64))
    tool_description = Column(Text)
    provider_type = Column(String)  # formerly "source_type"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_provider_tenant_id_name", "tenant_id", "name", unique=False),)

    resource_types = relationship(
        "ResourceTypeTable", back_populates=None, cascade="all, delete-orphan"
    )
