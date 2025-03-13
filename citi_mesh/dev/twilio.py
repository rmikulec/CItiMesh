import time
import os
import asyncio

from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

from citi_mesh.logging import get_logger
from citi_mesh.engine import CitiEngine
from citi_mesh.database.db_pool import DatabasePool
from citi_mesh.database.crud import get_tenant_from_name
from citi_mesh.engine.logistic_models import Analytic, OpenAIOutput
from citi_mesh.tools import CitiToolManager


logger = get_logger(__name__)

DatabasePool.get_instance()


def load_output_config() -> OpenAIOutput:
    logger.info("Loading base output config...")
    issue_type = Analytic(
        name="IssueType",
        description="The type of issue the citizen is reporting or asking about",
        value_type=str,
        possible_values=["Traffic", "Health", "Housing", "Food"],
    )

    severity = Analytic(
        name="Severity",
        description="The severity of the request or question the citizen asked",
        value_type=int,
    )

    OutputModel = OpenAIOutput.from_analytics(analytics=[issue_type, severity])

    return OutputModel


def load_tools(session):
    tenant = get_tenant_from_name(session=session, tenant_name="demo")
    return CitiToolManager(tools=["google_maps", "resources"], tenant=tenant, session=session)


class DevTwilioPoller:
    def __init__(
        self,
        local_endpoint,
        output_model,
        tools,
        polling_interval=1,
    ):
        """
        account_sid: Your Twilio Account SID.
        auth_token: Your Twilio Auth Token.
        local_endpoint: URL of your FastAPI endpoint (e.g. "http://localhost:8000/sms").
        polling_interval: How often (in seconds) to check for new messages.
        """
        self.client = Client(
            username=os.getenv("TWILIO_API_KEY", None),
            password=os.getenv("TWILIO_API_SECRET", None),
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        )
        self.local_endpoint = local_endpoint
        self.polling_interval = polling_interval
        # Keep track of messages we've already processed

        self.engine = CitiEngine(output_model=output_model, tools=tools)
        self.num_workers = 4
        self.queue = asyncio.Queue()

        self.active_numbers = set()
        self.processing_numbers = set()

        self.seen_messages = set()
        self.ready_messages = set()

    async def send_init_message(self, msg):
        message = await self.engine.get_init_message(phone=msg.from_, message=msg.body)
        self.client.messages.create(
            to=msg.from_,
            body=message,
            messaging_service_sid=os.getenv("TWILIO_MESSAGE_SERVICE_SID"),
        )
        logger.info(f"Response: {message}")

    async def send_processing_message(self, msg):
        message = await self.engine.get_processing_message(phone=msg.from_)
        self.client.messages.create(
            to=msg.from_,
            body=message,
            messaging_service_sid=os.getenv("TWILIO_MESSAGE_SERVICE_SID"),
        )
        logger.info(f"Response: {message}")

    async def worker(self):
        while True:
            msg = await self.queue.get()
            try:
                # If not an active number, send welcome text
                if msg.from_ not in self.active_numbers:
                    logger.info("New phone found...")
                    await self.send_init_message(msg)
                    await self.queue.put(msg)
                    self.active_numbers.add(msg.from_)
                # If number is not processing, then
                else:
                    if msg.sid in self.ready_messages:
                        await self.forward_message(msg)
                    else:
                        await self.send_processing_message(msg)
                        await self.queue.put(msg)
                        self.ready_messages.add(msg.sid)

            except Exception as e:
                logger.error(f"Error processing message from {msg.from_}: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    def init_messages(self):
        self.poll_new_messages()

    def poll_new_messages(self):
        """
        Retrieve a list of inbound messages from Twilio that haven't been processed yet.
        """
        messages = self.client.messages.list(
            to=os.getenv("TWILIO_NUMBER", None), date_sent_after=datetime.now()
        )
        new_messages = []
        for msg in messages:
            if msg.sid not in self.seen_messages:
                new_messages.append(msg)
                self.seen_messages.add(msg.sid)
        return new_messages

    async def polling_loop(self):
        while True:
            new_msgs = self.poll_new_messages()
            for msg in new_msgs:
                await self.queue.put(msg)
            await asyncio.sleep(self.polling_interval)

    async def forward_message(self, msg):
        """
        Mimic the behavior of a Twilio webhook call by sending the message details to your FastAPI endpoint.
        """
        # Construct a payload similar to what Twilio sends via webhook
        self.processing_numbers.add(msg.from_)
        try:
            logger.info(f"From: {msg.from_}, Body: {msg.body} \n")
            response = await self.engine.chat(phone=msg.from_, message=msg.body)
            self.client.messages.create(
                to=msg.from_,
                body=response.message,
                messaging_service_sid=os.getenv("TWILIO_MESSAGE_SERVICE_SID"),
            )
            logger.info(f"Response: {response.model_dump_json(indent=2)}")
            self.ready_messages.add(msg.sid)
        except Exception as e:
            logger.error(
                f"From: {msg.from_}, Body: {msg.body} \n    Error: {str(e)}", exc_info=True
            )
        finally:
            self.processing_numbers.remove(msg.from_)

    async def run(self):
        logger.info("Starting DevTwilioPoller...")
        self.init_messages()
        # Start polling and worker tasks concurrently
        poller_task = asyncio.create_task(self.polling_loop())
        worker_tasks = [asyncio.create_task(self.worker()) for _ in range(self.num_workers)]
        try:
            # Run indefinitely (or implement a stopping condition)
            await asyncio.gather(poller_task, *worker_tasks)
        except asyncio.CancelledError:
            # Optionally handle cleanup if the tasks are cancelled
            self.queue.shutdown()


# Example usage:
if __name__ == "__main__":
    with DatabasePool.get_session() as session:
        load_dotenv()
        LOCAL_ENDPOINT = "http://localhost:8000/sms"

        OutputModel = load_output_config()
        tools = load_tools(session)

        poller = DevTwilioPoller(LOCAL_ENDPOINT, OutputModel, tools)
        asyncio.run(poller.run())
