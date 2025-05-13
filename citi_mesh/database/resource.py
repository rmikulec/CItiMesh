import os
import googlemaps
import googlemaps
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
    resources = relationship(
        "ResourceTable", back_populates="tenant", cascade="all, delete-orphan"
    )


class ProviderTable(BaseTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    name = Column(String(length=64))
    provider_type = Column(String)  # formerly "source_type"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_provider_tenant_id_name", "tenant_id", "name", unique=False),)

    # Relationships
    tenant = relationship("TenantTable", back_populates="providers")
    resources = relationship(
        "ResourceTable", back_populates="provider", cascade="all, delete-orphan"
    )
    resource_types = relationship(
        "ResourceTypeTable", back_populates=None, cascade="all, delete-orphan"
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

    # Relationships
    tenant = relationship("TenantTable", back_populates="resources")
    provider = relationship("ProviderTable", back_populates="resources")
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


# --------------------------------------------------------------------
# Pydantic Models
# --------------------------------------------------------------------


class Address(FromDBModel):
    __ormclass__ = AddressTable

    street: str
    street2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    google_place_id: SkipJsonSchema[Optional[str]] = Field(default=None)

    @model_validator(mode="after")
    def get_google_place_id(self):
        """
        Example logic to auto-populate google_place_id
        (only if you really want to do this at model validation time).
        """
        client = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API"])
        address_str = (
            f"{self.street} {self.street2 or ''}, {self.city}, {self.state}, {self.zip_code}"
        )
        res = client.find_place(address_str, input_type="textquery")
        try:
            self.google_place_id = res["candidates"][0]["place_id"]
        except IndexError:
            self.google_place_id = None
        return self


class ResourceType(FromDBModel):
    __ormclass__ = ResourceTypeTable

    provider_id: str
    name: str
    display_name: str
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())



class Resource(FromDBModel):
    __ormclass__ = ResourceTable

    tenant_id: str
    provider_id: Optional[str] = None
    name: str
    description: str
    phone_number: Optional[str] = None
    website: Optional[str] = None
    address: Optional[Address] = None
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())

    # Many-to-many with ResourceType
    resource_types: List[ResourceType] = Field(default_factory=list)


class Provider(FromDBModel):
    __ormclass__ = ProviderTable

    tenant_id: str
    name: str
    display_name: str
    provider_type: str
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())

    # Relationship: resources
    resources: List["Resource"] = Field(default_factory=list)
    resource_types: List["ResourceType"] = Field(default_factory=list)


    def create_resource_from_openai_resource(
        self, openai_resource: "ResourceOpenAI", provider_id: str
    ) -> Resource:
        """
        Given an instance of the dynamically generated ResourceOpenAI (with enum-based resource_types),
        create a proper Resource Pydantic model that points to this Tenant and references the matching
        resource type objects from self.resource_types.

        Assumes:
        - self.get_resource_type(name: str) returns a Pydantic ResourceType or None if not found.
        - 'openai_resource' has the fields name, description, phone_number, website, address,
            and resource_types as a list of ResourceTypeEnum.
        """
        # Convert each enum member to its string value, then look up the corresponding ResourceType
        resolved_types = []
        for enum_value in openai_resource.resource_types:
            # enum_value.value is e.g. "Shelter" or "Food Pantry"
            rtype = self.get_resource_type(enum_value.value)
            if not rtype:
                raise ValueError(
                    f"No matching resource_type found for '{enum_value.value}' in tenant '{self.name}'"
                )
            resolved_types.append(rtype)

        # Build a new Resource referencing this tenant, using the openai_resource fields
        resource = Resource(
            tenant_id=self.id,
            provider_id=provider_id,
            name=openai_resource.name,
            description=openai_resource.description,
            phone_number=openai_resource.phone_number,
            website=openai_resource.website,
            address=openai_resource.address,  # if openai_resource includes an Address, re-use it
            resource_types=resolved_types,
        )
        return resource

    def get_resource_type(self, type_name):
        return list(filter(lambda rtype: rtype.name == type_name, self.resource_types))[0]


class Tenant(FromDBModel):
    __ormclass__ = TenantTable

    name: str
    display_name: str
    registered_number: str
    subdomain: str
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())

    providers: List[Provider] = Field(default_factory=list)
    resources: List[Resource] = Field(default_factory=list)


    def get_provider(self, provider_name: str):
        return list(filter(lambda provider: provider.name == provider_name, self.providers))[0]
