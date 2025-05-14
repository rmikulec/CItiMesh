from citi_mesh.logging import get_logger
from openai.types.chat import ParsedFunctionToolCall
import json

from citi_mesh.tools.base import CitimeshTool
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)



class CitiToolManager:

    def __init__(self, tools: list[CitimeshTool]):
        self.tools = {
            tool.tool_name: tool
            for tool in tools
        }


    def _get_tool(self, name: str):
        logger.info(f"Retrieving tool: {name}")
        tool = self.tools[name]
        return tool

    def to_openai(self):
        return [tool.to_openai() for tool in self.tools.values()]

    async def from_openai(self, tool_calls: list[ParsedFunctionToolCall], session: AsyncSession) -> list[dict[str, str]]:
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
                tool_response = await tool.call(session=session, **args)
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
