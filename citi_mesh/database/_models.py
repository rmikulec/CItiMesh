import os
from typing import List, Optional, Literal

import googlemaps
from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citi_mesh.database import _tables
from citi_mesh.database._base import SQLModel

"""
File contains all CRUD models to be used to access and change information in the database.

Models can also be used with FastAPI as Request / Response bodies
"""


class Address(SQLModel):
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
        client = googlemaps.Client(key=os.environ["GOOGLE_MAPS_KEY"])
        address_str = (
            f"{self.street} {self.street2 or ''}, {self.city}, {self.state}, {self.zip_code}"
        )
        res = client.find_place(address_str, input_type="textquery")
        try:
            self.google_place_id = res["candidates"][0]["place_id"]
        except IndexError:
            self.google_place_id = None
        return self


class ResourceType(SQLModel):
    __ormclass__ = _tables.ResourceTypeTable

    name: str
    display_name: str

    repository_id: SkipJsonSchema[str] = None


class Resource(SQLModel):
    __ormclass__ = _tables.ResourceTable

    tenant_id: str
    repository_id: Optional[str] = None
    name: str
    description: str
    phone_number: Optional[str] = None
    website: Optional[str] = None
    address: Optional[Address] = None

    # Many-to-many with ResourceType
    resource_types: List[ResourceType] = Field(default_factory=list)


class Repository(SQLModel):
    __ormclass__ = _tables.RepositoryTable

    tenant_id: str = None
    name: str
    display_name: str
    tool_description: str

    # Fields to not sure on request payload

    # Relationship: resources
    resource_types: List["ResourceType"] = Field(default_factory=list)

    def _get_resource_type(self, name):
        return list(filter(lambda r: r.name == name, self.resource_types))[0]

    def create_resource_from_openai_resource(self, openai_resource: "ResourceOpenAI") -> Resource:
        """
        Given an instance of the dynamically generated ResourceOpenAI with enum-based
        resource_types), create a proper Resource Pydantic model that points to this Tenant and
        references the matching resource type objects from self.resource_types.

        Assumes:
        - self.get_resource_type(name: str) returns a Pydantic ResourceType or None if not found.
        - 'openai_resource' has the fields name, description, phone_number, website, address,
            and resource_types as a list of ResourceTypeEnum.
        """
        # Convert each enum member to its string value, then look up the corresponding ResourceType
        resolved_types = []
        for enum_value in openai_resource.resource_types:
            # enum_value.value is e.g. "Shelter" or "Food Pantry"
            rtype = self._get_resource_type(enum_value.value)
            if not rtype:
                raise ValueError(
                    f"No matching resource_type found for '{enum_value.value}' in tenant '{self.name}'"  # noqa E501
                )
            resolved_types.append(rtype)

        # Build a new Resource referencing this tenant, using the openai_resource fields
        resource = Resource(
            tenant_id=self.id,
            repository_id=self.id,
            name=openai_resource.name,
            description=openai_resource.description,
            phone_number=openai_resource.phone_number,
            website=openai_resource.website,
            address=openai_resource.address,  # if openai_resource includes an Address, re-use it
            resource_types=resolved_types,
        )
        return resource

    async def get_resources_by_type(
        self, session: AsyncSession, resource_types: list[str]
    ) -> list[Resource]:
        """
        Queries the database for any resources associated with the Repository of
        types 'resource_types'

        args:
            - session(AsyncSession): An Async SQLAlchemy Session object
            - resource_types: A list of resource types associated with the Repository. Note, this
                does not check if the resource types are valid. Therefor, if types that do not
                exist, or are not linked with the repository are given, it will return an empty
                list

        returns:
            list[Resource]: A list of the requested resources
        """
        load_opts = self._build_load_options(_tables.ResourceTable, 2)
        stmt = (
            select(_tables.ResourceTable)
            .options(*load_opts)
            .join(
                _tables.ResourceTypeLinkTable,
                _tables.ResourceTypeLinkTable.resource_id == _tables.ResourceTable.id,
            )
            .join(
                _tables.ResourceTypeTable,
                _tables.ResourceTypeTable.id == _tables.ResourceTypeLinkTable.resource_type_id,
            )
            .where(
                (
                    _tables.ResourceTypeTable.name.in_(resource_types)
                    & (_tables.ResourceTable.repository_id == self.id)
                )
            )
        )
        instances = (await session.execute(stmt)).scalars()
        return [Resource.model_validate(instance) for instance in instances]


class Source(SQLModel):
    __ormclass__ = _tables.SourceTable
    repository_id: str
    source_type: str
    details: str


class AnalyticConfig(SQLModel):
    __ormclass__ = _tables.AnalyticConfigTable

    tenant_id: str
    name: str
    display_name: str
    description: str
    value_type: str
    possible_values: list[str] = Field(..., default_factory=list)

    @property
    def _values_enum(self):
        return Literal[tuple([v for v in self.possible_values])]

    @property
    def field_definition(self):
        if self.possible_values:
            return (self._values_enum, Field(..., description=self.description))

        else:
            return (self.value_type, Field(..., description=self.description))


class Tenant(SQLModel):
    __ormclass__ = _tables.TenantTable

    name: str
    display_name: str
    registered_number: str
    subdomain: str

    repositories: List[Repository] = Field(default_factory=list)
    analytics: list[AnalyticConfig] = Field(default_factory=list)

    def get_repository(self, repository_name: str):
        """
        Get a repository given a name
        """
        return list(
            filter(lambda repository: repository.name == repository_name, self.repositories)
        )[0]
