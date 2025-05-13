from citi_mesh.tools.maps import GoogleMapsDirectionsTool
from citi_mesh.tools.provider import ProviderTool
from citi_mesh.logging import get_logger
from enum import Enum
from openai.types.chat import ParsedFunctionToolCall
import json

from citi_mesh.database.models import Tenant
from citi_mesh.database.db_pool import DatabasePool
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class AvailableTools(Enum):
    GOOGLE_MAPS = GoogleMapsDirectionsTool
    RESOURCES = ProviderTool

    @classmethod
    def from_str(cls, name: str) -> "AvailableTools":
        """
        Look up an AvailableTools member by its name (case-insensitive).

        Args:
            name (str): The name of the tool (e.g., "google_maps").

        Returns:
            AvailableTools: The corresponding enum member.

        Raises:
            ValueError: If no matching tool is found.
        """
        try:
            return cls[name.strip().upper()]
        except KeyError:
            valid = ", ".join(member.name for member in cls)
            raise ValueError(f"'{name}' is not a valid tool. Valid options: {valid}")


class CitiToolManager:

    def __init__(self, tools: list[str], tenant: Tenant, session: Session):
        self.tools = {}

        for tool in tools:
            tool_instance = AvailableTools.from_str(tool).value(tenant=tenant, session=session)
            self.tools[tool_instance.tool_name] = tool_instance
            logger.info(f"{tool_instance.tool_name} Added")

    def _get_tool(self, name: str):
        logger.info(f"Retrieving tool: {name}")
        tool = self.tools[name]
        return tool

    def to_openai(self):
        return [tool.to_openai() for tool in self.tools.values()]

    def from_openai(self, tool_calls: list[ParsedFunctionToolCall], session: Session) -> list[dict[str, str]]:
        tool_messages = []
        for tool_call in tool_calls:
            logger.info(
                f"Calling tool {tool_call.function.name} with Args: {tool_call.function.arguments}"
            )
            tool = self._get_tool(tool_call.function.name)

            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            try:
                tool_response = tool.call(session=session, **args)
                logger.info(f"{tool.tool_name} Succeeded")
                tool_messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": tool_response}
                )
            except Exception as e:
                logger.error(f"Tool {tool.tool_name} Failed: {e}", exc_info=True)
                tool_messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": f"Tool call failed."}
                )

        return tool_messages
