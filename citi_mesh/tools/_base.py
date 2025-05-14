from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class CitimeshTool(ABC):
    """
    Base tool to be extended to create classes that are compatible with the Citimesh Tool Manager
    These tools automatically work, and can be called by OpenAI.

    Attributes:
        - tool_name(str): The name of the tool
        - tool_desc(str): A detailed description of the tool (This will be seen by the LLM)
        - args(dict): A jsonschema detailing the arguements for the tool

    """

    def __init__(
        self,
        tool_name: str,
        tool_desc: str,
        args: dict,
    ):
        self.tool_name = tool_name
        self.tool_desc = tool_desc
        self.args = args

    def to_openai(self):
        return {
            "type": "function",
            "strict": True,
            "function": {
                "strict": True,
                "name": self.tool_name,
                "description": self.tool_desc,
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": self.args,
                    "required": list(self.args.keys()),
                },
            },
        }

    @abstractmethod
    async def call(self, session: AsyncSession, *args, **kwargs) -> str:
        """
        Method to be extended in order to implement the behaviour of the tool.
        Method must be asynchronous and tool will get a Async SQLAlchemy session
        """
        pass
