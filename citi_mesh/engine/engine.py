import openai
import json
from typing import Type

from citi_mesh.engine.system_message import INITIAL_MESSAGE, PROCESSING_MESSAGE
from citi_mesh.engine.logistic_models import OpenAIOutput
from citi_mesh.engine.messages import MessageTracker
from citi_mesh.tools import CitiToolManager
from citi_mesh.config import Config


class CitiEngine:

    def __init__(self, output_model: Type[OpenAIOutput], tools: CitiToolManager):
        self.output_model = output_model
        self.client = openai.AsyncOpenAI()
        self.tools = tools

        self.messages = MessageTracker()

    def _load_from_db(self):
        pass

    def _upsert_to_db(self):
        pass

    async def chat(self, phone:str, message: str):
        self.messages.add(
            phone=phone,
            message={"role": "user", "content": message}
        )

        completion = await self.client.beta.chat.completions.parse(
            model=Config.chat_model,
            messages=self.messages.get(phone),
            response_format=self.output_model,
            tools=self.tools.to_openai(),
        )

        if completion.choices[0].message.tool_calls:
            self.messages.add(phone=phone, message=completion.choices[0].message)
            # Call tools and add messages
            self.messages.extend(
                phone=phone,
                messages=self.tools.from_openai(completion.choices[0].message.tool_calls)
            )

            completion = await self.client.beta.chat.completions.parse(
                model=Config.chat_model,
                messages=self.messages.get(phone),
                response_format=self.output_model,
                tools=self.tools.to_openai(),
            )

        output = completion.choices[0].message.parsed
        self.messages.add(
            phone=phone,
            message={'role': 'assistant', 'content': output.message}
        )

        return output 


    async def get_init_message(self, phone, message: str):
        completion = await self.client.chat.completions.create(
            messages=[
                {'role': 'system', 'content': INITIAL_MESSAGE},
                {'role': 'user', 'content': message}
            ],
            model=Config.chat_model
        )

        message = completion.choices[0].message.content

        self.messages.add(
            phone=phone,
            message={'role': 'assistant', 'content': message}
        )

        return message
    

    async def get_processing_message(self, phone):
        completion = await self.client.chat.completions.create(
            messages=[
                {'role': 'system', 'content': PROCESSING_MESSAGE},
                {'role': 'user', 'content': self.messages.get_conversation(phone)}
            ],
            model=Config.chat_model
        )

        message = completion.choices[0].message.content

        self.messages.add(
            phone=phone,
            message={'role': 'assistant', 'content': message}
        )

        return message


    def is_new_phone(self, phone) -> bool:
        return phone in self.messages.messages