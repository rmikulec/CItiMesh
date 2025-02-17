import time
import os
import asyncio

from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

from citi_mesh.engine import CitiEngine
from citi_mesh.engine.logistic_models import Analytic, OpenAIOutput


class DevTwilioPoller:
    def __init__(
        self, local_endpoint, output_model, polling_interval=1, use_whatsapp: bool = True
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
        self.processed_messages = set()

        self.engine = CitiEngine(output_model=output_model)

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
            if msg.sid not in self.processed_messages:
                new_messages.append(msg)
                self.processed_messages.add(msg.sid)
        return new_messages

    async def forward_message(self, msg):
        """
        Mimic the behavior of a Twilio webhook call by sending the message details to your FastAPI endpoint.
        """
        # Construct a payload similar to what Twilio sends via webhook
        payload = {
            "From": msg.from_,
            "To": msg.to,
            "Body": msg.body,
            "MessageSid": msg.sid,
            "AccountSid": msg.account_sid,
            # Optionally add more fields (e.g. NumMedia, DateSent, etc.)
        }
        try:
            response = await self.engine.chat(msg.body)
            self.client.messages.create(
                to=msg.from_,
                body=response.message,
                messaging_service_sid=os.getenv("TWILIO_MESSAGE_SERVICE_SID"),
            )
            print(
                f"From: {msg.from_}, Body: {msg.body} \n    message: {response.model_dump_json(indent=2)}"
            )
        except Exception as e:
            print(f"From: {msg.from_}, Body: {msg.body} \n    Error: {str(e)}")

    async def run(self):
        """
        Begin polling for new inbound messages. Each new message is forwarded to the local endpoint.
        """
        print("Starting DevTwilioPoller...")
        self.init_messages()
        while True:
            new_msgs = self.poll_new_messages()
            if new_msgs:
                for msg in new_msgs:
                    await self.forward_message(msg)
            time.sleep(self.polling_interval)


# Example usage:
if __name__ == "__main__":
    load_dotenv()
    LOCAL_ENDPOINT = "http://localhost:8000/sms"

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

    poller = DevTwilioPoller(LOCAL_ENDPOINT, OutputModel)
    asyncio.run(poller.run())
