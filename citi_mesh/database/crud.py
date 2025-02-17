from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.database.resource import TenantTable, Tenant, AddressTable, Address


class NotFoundInDatabase(Exception):
    """
    Exception to raise when an entry is not found in the database
    """

    def __init__(self, table: str, column: str, value: str):
        message = f"No entries found in {table} with {column} as {value}"

        super().__init__(message)


def get_tenant_from_name(name: str) -> Tenant:
    """
    Gets a tenant from the database given a unique name
    """
    with DatabasePool.get_instance().get_session() as session:
        tenant_instance = session.query(TenantTable).filter(TenantTable.name == name).first()

        if tenant_instance:
            return Tenant.model_validate(tenant_instance)
        else:
            raise NotFoundInDatabase(table="Tenant", column="name", value=name)
