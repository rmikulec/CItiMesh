import os
from datetime import datetime
from typing import Callable

from twilio.rest import Client

from citi_mesh.logging import get_logger

LOGGER = get_logger("[CLIENT]")

def json_serializer(o):
    if isinstance(o, datetime):
        return o.isoformat()
    else:
        return o


async def send_message_twilio(to: str, message_func: Callable, *args, **kwargs):
    """
    Helper function to use the Twilio API in order to send a message through their servers
    """
    client = Client(
        username=os.getenv("TWILIO_API_KEY", None),
        password=os.getenv("TWILIO_API_SECRET", None),
        account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
    )
    message = await message_func(*args, **kwargs)

    client.messages.create(
        to=to,
        body=message,
        messaging_service_sid=os.getenv("TWILIO_MESSAGE_SERVICE_SID"),
    )


async def send_message_console(to: str, message_func: Callable, *args, **kwargs):
    message = await message_func(*args, **kwargs)
    LOGGER.info(message)