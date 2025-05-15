import threading
from typing import Type

import openai
from sqlalchemy.ext.asyncio import AsyncSession

from citi_mesh.config import Config
from citi_mesh.engine.output_model import OpenAIOutput
from citi_mesh.engine.messages import MessageTracker
from citi_mesh.engine.system_message import INITIAL_MESSAGE, PROCESSING_MESSAGE
from citi_mesh.logging import get_logger
from citi_mesh.tools import CitiToolManager, GoogleMapsDirectionsTool, RepositoryTool
from citi_mesh.database._models import Tenant
from citi_mesh.database.session import get_session

logger = get_logger(__name__)


class CitiEngine:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(
        cls,
    ) -> "CitiEngine":
        # Double‑checked locking in __new__
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
    ) -> None:
        # Ensure init runs only once
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        logger.info("Starting up CitiEngine…")
        self.message_tracker = MessageTracker(expiration_minutes=Config.conversation_expiration)
        self.tool_manager = CitiToolManager()
        self.client = openai.AsyncOpenAI()


    async def init(self, tenant_id: str, session: AsyncSession):
        # Set up tools: Pull all repositories
        tenant = await Tenant.from_id(session=session, id_=tenant_id)
        for repository in tenant.repositories:
            self.tool_manager.add_tool(
                RepositoryTool(
                    repository=repository
                )
            )
        # Add the google maps tool
        self.tool_manager.add_tool(
            GoogleMapsDirectionsTool()
        )

        # Setup Output configs
        self.output_model = OpenAIOutput.from_analytics(tenant.analytics)



    async def chat(self, phone: str, message: str) -> OpenAIOutput:
        with self._lock:
            self.message_tracker.add(phone=phone, message={"role": "user", "content": message})

            completion = await self.client.beta.chat.completions.parse(
                model=Config.chat_model,
                messages=self.message_tracker.get(phone),
                response_format=self.output_model,
                tools=self.tool_manager.to_openai(),
            )

            if completion.choices[0].message.tool_calls:
                self.message_tracker.add(phone=phone, message=completion.choices[0].message)
                # Call tools and add messages
                async with get_session() as session:
                    tool_messages = await self.tool_manager.from_openai(
                        tool_calls=completion.choices[0].message.tool_calls,
                        session=session
                    )
                self.message_tracker.extend(
                    phone=phone,
                    messages=tool_messages,
                )

                completion = await self.client.beta.chat.completions.parse(
                    model=Config.chat_model,
                    messages=self.message_tracker.get(phone),
                    response_format=self.output_model,
                    tools=self.tool_manager.to_openai(),
                )

            output = completion.choices[0].message.parsed
            self.message_tracker.add(
                phone=phone, message={"role": "assistant", "content": output.message}
            )

            return output.message

    async def get_init_message(self, phone, message: str):
        completion = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": INITIAL_MESSAGE},
                {"role": "user", "content": message},
            ],
            model=Config.chat_model,
        )

        message = completion.choices[0].message.content

        self.message_tracker.add(phone=phone, message={"role": "assistant", "content": message})

        return message

    async def get_processing_message(self, phone: str, message: str):
        user_message = (
            f"Here is the current conversation: {self.message_tracker.get_conversation(phone)}"
            f"Here is the incoming message: {message}"
        )

        completion = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": PROCESSING_MESSAGE},
                {"role": "user", "content": user_message},
            ],
            model=Config.chat_model,
        )

        message = completion.choices[0].message.content

        with self._lock:
            self.message_tracker.add(
                phone=phone, message={"role": "assistant", "content": message}
            )

        return message

    def is_new_phone(self, phone) -> bool:
        return phone in self.message_tracker.messages
