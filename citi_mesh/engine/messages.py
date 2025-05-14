from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from citi_mesh.engine.system_message import SYSTEM_MESSAGE


@dataclass
class MessageArray:
    messages: List[Dict]
    last_updated: datetime


class MessageTracker:
    def __init__(self, expiration_minutes: int = 5):
        """
        Initializes the MessageTracker.

        :param expiration_minutes: Number of minutes after which an unused
                                   phone number's messages are cleared.
        """
        self.expiration_delta = timedelta(minutes=expiration_minutes)
        self.messages: Dict[str, MessageArray] = {}  # Maps phone numbers to MessageArray

    def remove_phone(self, phone: str):
        """
        Removes the messages for a specific phone number.

        :param phone: The phone number as a string.
        """
        if phone in self.messages:
            del self.messages[phone]

    def _cleanup(self):
        """
        Removes any phone number entries that haven't been updated within the expiration period.
        """
        now = datetime.now()
        # Identify phone numbers that have expired
        to_delete = [
            phone
            for phone, msg_array in self.messages.items()
            if now - msg_array.last_updated > self.expiration_delta
        ]
        for phone in to_delete:
            self.remove_phone(phone)

    def add(self, phone: str, message: Dict):
        """
        Adds a message (as a dictionary) for the given phone number.
        Updates the last_updated time for that phone number.

        :param phone: The phone number as a string.
        :param message: The message to add (as a dictionary).
        """
        now = datetime.now()
        if phone not in self.messages:
            system_message = {"role": "system", "content": SYSTEM_MESSAGE}
            self.messages[phone] = MessageArray(messages=[system_message], last_updated=now)
        self.messages[phone].messages.append(message)
        self.messages[phone].last_updated = now

    def extend(self, phone: str, messages: list[dict]):
        """
        Adds a message (as a dictionary) for the given phone number.
        Updates the last_updated time for that phone number.

        :param phone: The phone number as a string.
        :param message: The message to add (as a dictionary).
        """
        now = datetime.now()
        if phone not in self.messages:
            system_message = [{"role": "system", "content": SYSTEM_MESSAGE}]
            self.messages[phone] = MessageArray(messages=[system_message], last_updated=now)
        self.messages[phone].messages.extend(messages)
        self.messages[phone].last_updated = now

    def get(self, phone: str) -> Optional[List[Dict]]:
        """
        Retrieves the list of messages for the given phone number.
        Updates the last_updated time if the phone number exists.

        :param phone: The phone number as a string.
        :return: A list of messages or None if the phone number doesn't exist.
        """
        if phone in self.messages:
            self.messages[phone].last_updated = datetime.now()
            return self.messages[phone].messages
        return None

    def clear_all(self):
        """
        Clears all phone numbers and their messages.
        """
        self.messages.clear()

    def get_conversation(self, phone: str) -> str:
        if phone not in self.messages:
            return "Conversation just started"
        else:
            conv_str = ""
            for message in self.get(phone):
                if isinstance(message, dict):
                    if message["role"] == "assistant":
                        conv_str += f"\n Assistant: {message['content']}"
                    elif message["role"] == "user":
                        conv_str += f"\n User: {message['content']}"
            return conv_str
