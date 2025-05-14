import os
import googlemaps
import googlemaps
from datetime import datetime
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from citi_mesh.database import _tables
from citi_mesh.database.base import FromDBModel


class Address(FromDBModel):
    __ormclass__ = _tables.AddressTable

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
    __ormclass__ = _tables.ResourceTypeTable

    provider_id: str
    name: str
    display_name: str
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())



class Resource(FromDBModel):
    __ormclass__ = _tables.ResourceTable

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
    __ormclass__ = _tables.ProviderTable

    name: str
    display_name: str
    tool_description: str

    # Fields to not sure on request payload
    tenant_id: SkipJsonSchema[str]
    provider_type: SkipJsonSchema[str]
    created_at: SkipJsonSchema[datetime] = Field(default=datetime.now())
    updated_at: SkipJsonSchema[datetime] = Field(default=datetime.now())

    # Relationship: resources
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

    
    async def get_resources_by_type(self, session: AsyncSession, resource_types: list[str]):
        load_opts = self._build_load_options(_tables.ResourceTable, 2)
        stmt = (
            select(_tables.ResourceTable)
            .options(*load_opts)
            .join(_tables.ResourceTypeLinkTable, _tables.ResourceTypeLinkTable.resource_id == _tables.ResourceTable.id)
            .join(_tables.ResourceTypeTable, _tables.ResourceTypeTable.id == _tables.ResourceTypeLinkTable.resource_type_id)
            .where((_tables.ResourceTypeTable.name.in_(resource_types) & (_tables.ResourceTable.provider_id==self.id)))
        )
        instances = (await session.execute(stmt)).scalars()

        return [
            Resource.model_validate(instance)
            for instance in instances
        ]


class Tenant(FromDBModel):
    __ormclass__ = _tables.TenantTable

    name: str
    display_name: str
    registered_number: str
    subdomain: str
    created_at: datetime = Field(default=datetime.now())
    updated_at: datetime = Field(default=datetime.now())

    providers: List[Provider] = Field(default_factory=list)

    def get_provider(self, provider_name: str):
        return list(filter(lambda provider: provider.name == provider_name, self.providers))[0]
