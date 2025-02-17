from citi_mesh.tools.maps import GoogleMapsDirectionsTool
from enum import Enum
from openai.types.chat import ParsedFunctionToolCall
import json


class AvailableTools(Enum):
    GOOGLE_MAPS = GoogleMapsDirectionsTool

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

    def __init__(self, tools: list[str]):
        self.tools = [AvailableTools.from_str(tool).value() for tool in tools]

    def _get_tool(self, name: str):
        for tool in self.tools:
            if name == tool.tool_name:
                return tool

    def to_openai(self):
        return [tool.to_openai() for tool in self.tools]

    def from_openai(self, tool_calls: list[ParsedFunctionToolCall]) -> list[dict[str, str]]:
        tool_messages = []
        for tool_call in tool_calls:
            tool = self._get_tool(tool_call.function.name)

            try:
                args = json.loads(tool_call.function.arguments)
                print(args)
            except json.JSONDecodeError:
                args = {}

            tool_response = tool.call(**args)
            tool_messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": tool_response}
            )

        return tool_messages
