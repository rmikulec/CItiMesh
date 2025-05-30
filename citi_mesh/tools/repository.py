import json

from sqlalchemy.ext.asyncio import AsyncSession

from citi_mesh.database._models import Repository
from citi_mesh.logging import get_logger
from citi_mesh.tools._base import CitimeshTool
from citi_mesh.utils import json_serializer

logger = get_logger(__name__)


class RepositoryTool(CitimeshTool):
    """
    Allows CitiEngine to access data from a Repository.
    """

    def __init__(
        self,
        repository: Repository,
        require_resource_type: bool = True,
    ):

        # Set the repository
        self.repository = repository
        resource_types = [rtype.name for rtype in repository.resource_types]
        if not require_resource_type:
            resource_types.extend("n/a")

        # Set the arguemnets detialing to the LLM how to retrieve data from it
        args = {
            "resource_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": resource_types,
                },
                "description": f"The types of {repository.display_name}. Can pick more than one if needed.",
            }
        }

        super().__init__(
            tool_name=f"get_{repository.name}",
            tool_desc=repository.tool_description,
            args=args,
        )

    async def call(self, session: AsyncSession, resource_types: list[str]) -> str:
        """
        This 'call' function will query the database for all resources of the requested types by
        the LLM. It will then package up all the data into a well formatted JSON string
        """
        resources = await self.repository.get_resources_by_type(session, resource_types)

        return json.dumps(
            [
                resource.model_dump(
                    exclude=[
                        "id",
                        "tenant_id",
                        "repository_id",
                        "created_at",
                        "updated_at",
                        "resource_types",
                    ]
                )
                for resource in resources
            ],
            indent=2,
            default=json_serializer,
        )
