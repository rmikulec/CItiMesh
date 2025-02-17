from abc import ABC, abstractmethod


class BaseCitimeshTool(ABC):

    def __init__(self, tool_name: str, tool_desc: str, args: dict):
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
    def call(self, *args, **kwargs):
        pass
