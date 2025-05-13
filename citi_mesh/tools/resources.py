import json

from sqlalchemy.orm import Session

from citi_mesh.logging import get_logger
from citi_mesh.utils import json_serializer
from citi_mesh.tools.base import CitimeshTool
from citi_mesh.database.crud import (
    get_all_resources_for_tenant_by_types,
    get_all_resources_for_provider_by_types,
)
from citi_mesh.database.resource import Tenant
from citi_mesh.database.resource import Provider

logger = get_logger(__name__)


class ProviderTool(CitimeshTool):
    """
    Allows CitiEngine to access data from a Provider.
    """

    def __init__(
        self,
        tenant: Tenant,
        provider: Provider,
        use_provider_names: bool = False,
        require_resource_type: bool = True,
        require_provider_name: bool = False,
    ):

        logger.info(f"TenantID from tool: {tenant.id}")

        resource_types = [rtype.name for rtype in tenant.resource_types]
        if not require_resource_type:
            resource_types.extend("n/a")

        args = {
            provider.name: {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": resource_types,
                },
                "description": "The type of service needed. Can pick more than one if needed.",
            }
        }

        if use_provider_names:
            provider_names = [provider.name for provider in tenant.providers]
            if not require_provider_name:
                provider_names.extend("n/a")

            args["provider_name"] = {
                "type": "string",
                "enum": provider_names,
                "description": "Name of the provider to the data. This is where the information is from. Respond with 'n/a' if not applicable",
            }

        super().__init__(
            tool_name="get_local_services",
            tool_desc="Gets information on local services (including non-profits, charities, community organziations, etc)",
            args=args,
        )
        self.tenant = tenant

    def call(self, session: Session, service_types: list[str], provider_name: str = None) -> str:
        logger.info(f"TenantID from tool: {self.tenant.id}")
        if provider_name:
            resources = get_all_resources_for_provider_by_types(
                session=self.session,
                provider_id=self.tenant.get_provider(provider_name).id,
                resource_type_names=service_types,
            )
        else:
            resources = get_all_resources_for_tenant_by_types(
                session=self.session, resource_type_names=service_types, tenant_id=self.tenant.id
            )

        return json.dumps(
            [
                resource.model_dump(
                    exclude=["id", "tenant_id", "provider_id", "created_at", "updated_at"]
                )
                for resource in resources
            ],
            indent=2,
            default=json_serializer,
        )
