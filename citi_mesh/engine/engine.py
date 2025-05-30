import threading
from typing import Type

import openai

from citi_mesh.config import Config
from citi_mesh.engine.analytic_models import OpenAIOutput
from citi_mesh.engine.messages import MessageTracker
from citi_mesh.engine.system_message import INITIAL_MESSAGE, PROCESSING_MESSAGE
from citi_mesh.logging import get_logger
from citi_mesh.tools import CitiToolManager

logger = get_logger(__name__)


class CitiEngine:
    _instance = None
    _lock = threading.Lock()
    _message_tracker = None
    _client = None
    _output_model = None
    _tool_manager = None

    @classmethod
    def get_instance(
        cls,
        output_model: Type[OpenAIOutput],
        tool_manager: CitiToolManager,
        conversation_expiration: int = 5,
    ):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    logger.info("Starting up CitiEngine...")
                    cls._instance = cls()
                    cls._message_tracker = MessageTracker(
                        expiration_minutes=conversation_expiration
                    )
                    cls._client = openai.AsyncOpenAI()
                    cls._output_model = output_model
                    cls._tool_manager = tool_manager
        return cls._instance

    @classmethod
    async def chat(cls, phone: str, message: str) -> OpenAIOutput:
        with cls._lock:
            cls._message_tracker.add(phone=phone, message={"role": "user", "content": message})

            completion = await cls._client.beta.chat.completions.parse(
                model=Config.chat_model,
                messages=cls._message_tracker.get(phone),
                response_format=cls._output_model,
                tools=cls._tool_manager.to_openai(),
            )

            if completion.choices[0].message.tool_calls:
                cls._message_tracker.add(phone=phone, message=completion.choices[0].message)
                # Call tools and add messages
                cls._message_tracker.extend(
                    phone=phone,
                    messages=cls._tool_manager.from_openai(
                        completion.choices[0].message.tool_calls
                    ),
                )

                completion = await cls._client.beta.chat.completions.parse(
                    model=Config.chat_model,
                    messages=cls._message_tracker.get(phone),
                    response_format=cls._output_model,
                    tools=cls._tool_manager.to_openai(),
                )

            output = completion.choices[0].message.parsed
            cls._message_tracker.add(
                phone=phone, message={"role": "assistant", "content": output.message}
            )

            return output.message

    @classmethod
    async def get_init_message(cls, phone, message: str):
        completion = await cls._client.chat.completions.create(
            messages=[
                {"role": "system", "content": INITIAL_MESSAGE},
                {"role": "user", "content": message},
            ],
            model=Config.chat_model,
        )

        message = completion.choices[0].message.content

        cls._message_tracker.add(phone=phone, message={"role": "assistant", "content": message})

        return message

    @classmethod
    async def get_processing_message(cls, phone: str, message: str):

        user_message = (
            f"Here is the current conversation: {cls._message_tracker.get_conversation(phone)}"
            f"Here is the incoming message: {message}"
        )

        completion = await cls._client.chat.completions.create(
            messages=[
                {"role": "system", "content": PROCESSING_MESSAGE},
                {"role": "user", "content": user_message},
            ],
            model=Config.chat_model,
        )

        message = completion.choices[0].message.content

        with cls._lock:
            cls._message_tracker.add(
                phone=phone, message={"role": "assistant", "content": message}
            )

        return message

    @classmethod
    def is_new_phone(cls, phone) -> bool:
        return phone in cls._message_tracker.messages
