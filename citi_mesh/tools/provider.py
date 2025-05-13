import json

from sqlalchemy.orm import Session

from citi_mesh.logging import get_logger
from citi_mesh.utils import json_serializer
from citi_mesh.tools.base import CitimeshTool
from citi_mesh.database.models import Provider

logger = get_logger(__name__)


class ProviderTool(CitimeshTool):
    """
    Allows CitiEngine to access data from a Provider.
    """

    def __init__(
        self,
        provider: Provider,
        require_resource_type: bool = True,
    ):

        self.provider = provider
        resource_types = [rtype.name for rtype in provider.resource_types]
        if not require_resource_type:
            resource_types.extend("n/a")

        args = {
            'resource_types': {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": resource_types,
                },
                "description": f"The types of {provider.display_name}. Can pick more than one if needed.",
            }
        }


        super().__init__(
            tool_name=f"get_{provider.name}",
            tool_desc=provider.tool_description,
            args=args,
        )
    

    async def call(self, session: Session, resource_types: list[str]) -> str:
        resources = await self.provider.get_resources_by_type(session, resource_types)

        return json.dumps(
            [
                resource.model_dump(
                    exclude=["id", "tenant_id", "provider_id", "created_at", "updated_at", "resource_types"]
                )
                for resource in resources
            ],
            indent=2,
            default=json_serializer,
        )
