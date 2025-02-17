import openai
from typing import Type

from citi_mesh.engine.system_message import SYSTEM_MESSAGE
from citi_mesh.engine.logistic_models import OpenAIOutput
from citi_mesh.tools import CitiToolManager


class CitiEngine:

    def __init__(self, output_model: Type[OpenAIOutput], tools: CitiToolManager):
        self.output_model = output_model
        self.client = openai.AsyncOpenAI()
        self.tools = tools

        self.messages = [{"role": "system", "content": SYSTEM_MESSAGE}]

    def _load_from_db(self):
        pass

    def _upsert_to_db(self):
        pass

    async def chat(self, message: str):
        self.messages.append({"role": "user", "content": message})

        completion = await self.client.beta.chat.completions.parse(
            model="o1",
            messages=self.messages,
            response_format=self.output_model,
            tools=self.tools.to_openai(),
        )

        self.messages.append(completion.choices[0].message)

        if completion.choices[0].message.tool_calls:
            self.messages.extend(self.tools.from_openai(completion.choices[0].message.tool_calls))

            completion = await self.client.beta.chat.completions.parse(
                model="o1",
                messages=self.messages,
                response_format=self.output_model,
                tools=self.tools.to_openai(),
            )

        return completion.choices[0].message.parsed
