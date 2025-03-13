from typing import List, Optional
from sqlalchemy.orm import Session

from typing import List, Optional
from sqlalchemy.orm import Session

from citi_mesh.database.resource import (
    Tenant,
    Provider,
    Resource,
    TenantTable,
    ResourceTable,
    ResourceTypeTable,
)


def create_tenant_with_resource_types(session: Session, tenant_data: Tenant) -> Tenant:
    """
    Creates a new Tenant (and any nested ResourceType objects) in the database
    from a Pydantic Tenant model.

    :param session: SQLAlchemy session
    :param tenant_data: Pydantic Tenant object with .resource_types populated
    :return: Newly-created Tenant as a Pydantic model (with updated IDs, timestamps, etc.)
    """
    # Convert to a SQLAlchemy TenantTable instance
    tenant_orm = tenant_data.to_orm()

    # Persist
    session.add(tenant_orm)
    session.commit()
    session.refresh(tenant_orm)

    # Convert back to Pydantic
    return Tenant.model_validate(tenant_orm, from_attributes=True)


def create_provider_with_resources(session: Session, provider_data: Provider) -> Provider:
    """
    Creates a new Provider and its nested Resource objects (and any nested ResourceTypes)
    from a Pydantic Provider model.

    :param session: SQLAlchemy session
    :param provider_data: Pydantic Provider object with .resources
                         (and possibly each Resource containing .resource_types).
    :return: Newly-created Provider as a Pydantic model
    """
    # Convert to a SQLAlchemy ProviderTable instance
    provider_orm = provider_data.to_orm()

    # Persist
    session.add(provider_orm)
    session.commit()
    session.refresh(provider_orm)

    # Convert back to Pydantic
    return Provider.model_validate(provider_orm, from_attributes=True)


def get_tenant_with_resource_types_and_providers(
    session: Session, tenant_id: str
) -> Optional[Tenant]:
    """
    Loads a Tenant by ID, then returns it as a Pydantic Tenant model.
    Will include the tenant's resource_types and providers, but
    .resources won't be auto-accessed unless you explicitly load them.
    """
    # Eager-load resource_types and providers but not resources
    tenant_orm = (
        session.query(TenantTable)
        .filter_by(id=tenant_id)
        .options(
            # optional: joinedload(TenantTable.resource_types),
            # optional: joinedload(TenantTable.providers),
            # or subqueryload(...) if desired
        )
        .one_or_none()
    )
    if not tenant_orm:
        return None

    # Convert to Pydantic
    return Tenant.model_validate(tenant_orm, from_attributes=True)


def get_tenant_from_name(session: Session, tenant_name: str) -> Optional[Tenant]:
    """
    Loads a Tenant by ID, then returns it as a Pydantic Tenant model.
    Will include the tenant's resource_types and providers, but
    .resources won't be auto-accessed unless you explicitly load them.
    """
    # Eager-load resource_types and providers but not resources
    tenant_orm = (
        session.query(TenantTable)
        .filter_by(name=tenant_name)
        .options(
            # optional: joinedload(TenantTable.resource_types),
            # optional: joinedload(TenantTable.providers),
            # or subqueryload(...) if desired
        )
        .one_or_none()
    )
    if not tenant_orm:
        return None

    # Convert to Pydantic
    return Tenant.model_validate(tenant_orm, from_attributes=True)


def get_all_resources_from_tenant(session: Session, tenant_id: str) -> List[Resource]:
    """
    Fetches all resources belonging to a given tenant,
    returns them as a list of Pydantic Resource models.
    """
    resources_orm = session.query(ResourceTable).filter_by(tenant_id=tenant_id).all()

    return [Resource.model_validate(r, from_attributes=True) for r in resources_orm]


def get_all_resources_from_provider(session: Session, provider_id: str) -> List[Resource]:
    """
    Fetches all resources belonging to a given provider,
    returns them as a list of Pydantic Resource models.
    """
    resources_orm = session.query(ResourceTable).filter_by(provider_id=provider_id).all()

    return [Resource.model_validate(r, from_attributes=True) for r in resources_orm]


def get_all_resources_for_tenant_by_types(
    session: Session, tenant_id: str, resource_type_names: List[str]
) -> List[Resource]:
    """
    Returns all resources for a tenant that match any of the given resource types.
    Uses a join to ResourceTypeTable by name, filtering by tenant_id as well.
    """
    # We join ResourceTable -> ResourceType via the many-to-many
    resources_orm = (
        session.query(ResourceTable)
        .join(ResourceTable.resource_types)  # resource_type_link automatically
        .filter(ResourceTable.tenant_id == tenant_id)
        .filter(ResourceTypeTable.name.in_(resource_type_names))
        .distinct()
        .all()
    )

    return [Resource.model_validate(r, from_attributes=True) for r in resources_orm]


def get_all_resources_for_provider_by_types(
    session: Session, provider_id: str, resource_type_names: List[str]
) -> List[Resource]:
    """
    Returns all resources for a provider that match any of the given resource types.
    """
    resources_orm = (
        session.query(ResourceTable)
        .join(ResourceTable.resource_types)
        .filter(ResourceTable.provider_id == provider_id)
        .filter(ResourceTypeTable.name.in_(resource_type_names))
        .distinct()
        .all()
    )

    return [Resource.model_validate(r, from_attributes=True) for r in resources_orm]
