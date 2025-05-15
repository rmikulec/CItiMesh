from sqlalchemy import Column, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from citi_mesh.database._base import SQLTable

"""
File contains all table definitions to be created in the database
"""


class TenantTable(SQLTable):
    name = Column(String(length=32), unique=True, index=True)
    display_name = Column(String(length=32), unique=True)
    registered_number = Column(String(length=17), unique=True)
    subdomain = Column(String(length=16), unique=True)

    # Relationships
    repositories = relationship(
        "RepositoryTable", back_populates=None, cascade="all, delete-orphan"
    )

    analytics = relationship(
        "AnalyticConfigTable", back_populates=None, cascade="all, delete-orphan"
    )


class ResourceTypeTable(SQLTable):
    repository_id = Column(String(length=128), ForeignKey("repository.id"))
    name = Column(String(length=64))
    display_name = Column(String)  # formerly "name_pretty"

    __table_args__ = (
        Index("idx_resource_type_repository_id_name", "repository_id", "name", unique=False),
    )

    # Many-to-many link back to resources
    resources = relationship(
        "ResourceTable", secondary="resource_type_link", back_populates="resource_types"
    )


class ResourceTable(SQLTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    repository_id = Column(String(length=128), ForeignKey("repository.id"), nullable=True)
    name = Column(String(length=128))
    description = Column(Text)
    phone_number = Column(String)
    website = Column(String)
    address_id = Column(String(length=128), ForeignKey("address.id"), nullable=True)

    address = relationship("AddressTable", back_populates="resources")

    resource_types = relationship(
        "ResourceTypeTable", secondary="resource_type_link", back_populates="resources"
    )


class ResourceTypeLinkTable(SQLTable):
    # Composite PK of (resource_id, resource_type_id)
    resource_id = Column(String(length=128), ForeignKey("resource.id"), primary_key=True)
    resource_type_id = Column(String(length=128), ForeignKey("resource_type.id"), primary_key=True)


class AddressTable(SQLTable):
    street = Column(String(128))
    street2 = Column(String(128), nullable=True)
    city = Column(String(64))
    state = Column(String(16))  # e.g. US state abbreviations
    zip_code = Column(String(10))
    google_place_id = Column(String, nullable=True)

    # Relationships
    resources = relationship("ResourceTable", back_populates="address")


class RepositoryTable(SQLTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    name = Column(String(length=64))
    display_name = Column(String(length=64))
    tool_description = Column(Text)

    __table_args__ = (Index("idx_repository_tenant_id_name", "tenant_id", "name", unique=False),)

    resource_types = relationship(
        "ResourceTypeTable", back_populates=None, cascade="all, delete-orphan"
    )


class AnalyticConfigTable(SQLTable):
    tenant_id = Column(String, ForeignKey("tenant.id"))
    name = Column(String(length=32), unique=True)
    display_name = Column(String(length=32), unique=True)
    description = Column(Text)
    value_type = Column(String(length=16))

    possible_values = relationship("AnalyticValueEnumsTable", back_populates=None, cascade="all, delete-orphan")


class AnalyticValueEnumsTable(SQLTable):
    analytic_id = Column(String, ForeignKey("analytic_config.id"))
    value = Column(String)


class SourceTable(SQLTable):
    repository_id = Column(String, ForeignKey("repository.id"))
    source_type = Column(String)
    details = Column(String)
