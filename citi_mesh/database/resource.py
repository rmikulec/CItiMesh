import os
import googlemaps

from typing import Optional
from citi_mesh.database.base import BaseTable, FromDBModel
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema


"""
Classes for SQLAlchemy, these define the database schema
"""


class AddressTable(BaseTable):
    street1 = Column(String(128))
    street2 = Column(String(128), nullable=True)
    city = Column(String(64))
    state = Column(String(16))  # Assuming US state abbreviations
    postal_code = Column(String(10))
    google_place_id = Column(String)


class TenantTable(BaseTable):
    name = Column(String(length=32), unique=True)
    registered_number = Column(String(length=17), unique=True)
    url_extension = Column(String(length=16), unique=True)


class ResourceProviderTable(BaseTable):
    tenant_id = Column(String(length=128), ForeignKey("tenant.id"))
    name = Column(String)
    source_type = Column(String)
    date_uploaded = Column(DateTime)

    resources = relationship("ResourceTable", back_populates=None)


class ResourceTable(BaseTable):
    provider_id = Column(String(length=128), ForeignKey("resource_provider.id"))
    name = Column(String)
    resource_type = Column(String)
    description = Column(Text)
    phone_number = Column(String)
    website = Column(String)
    address_id = Column(String(128), ForeignKey("address.id"), nullable=True)

    address = relationship("AddressTable", back_populates=None)


"""
Classes for Pydantic, these define the OpenAI and API interactions

They must be linked properly the the Table classes
"""


class Address(FromDBModel):
    __ormclass__ = AddressTable

    street1: str
    street2: str
    city: str
    state: str
    postal_code: str
    google_place_id: SkipJsonSchema[Optional[str]] = Field(default=None)

    @model_validator(mode="after")
    def get_google_place_id(self):
        client = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API"])
        address_str = (
            f"{self.street1} {self.street2}, {self.city}, {self.state}, {self.postal_code}"
        )
        res = client.find_place(address_str, input_type="textquery")
        try:
            self.google_place_id = res["candidates"][0]["place_id"]
        except IndexError:
            self.google_place_id = None
        return self


class Resource(FromDBModel):
    __ormclass__ = ResourceTable

    provider_id: SkipJsonSchema[str] = Field(default=None)
    name: str
    resource_type: str
    description: str
    phone_number: str
    website: str
    address: Optional[Address] = Field(default=None)


class ResourceProvider(FromDBModel):
    __ormclass__ = ResourceProviderTable

    tenant_id: str
    name: str
    source_type: str
    date_uploaded: datetime = Field(default=datetime.now())

    resources: list[Resource]


class Tenant(FromDBModel):
    __ormclass__ = TenantTable

    name: str
    registered_number: str
    url_extension: str
