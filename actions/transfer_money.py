from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, BotUttered
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.types import DomainDict

from actions.db import add_contact, get_contacts, Contact

all_recipients = [
    {
        "name": "John",
        "iban": "DE1234567890",
        "phone_number": "12345"
    }
]


class AddNewRecipient(Action):
    def name(self) -> str:
        return "add_new_recipient"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:

        new_recipient_details = {
            "name": tracker.get_slot("recipient_name"),
            "iban": tracker.get_slot("recipient_iban"),
            "phone_number": tracker.get_slot("recipient_phone_number")
        }
        global all_recipients
        all_recipients.append(new_recipient_details)

        return [BotUttered("Recipient added")]


class SendMoney(Action):
    def name(self) -> str:
        return "send_money"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:

        return [BotUttered(f"Executing transfer to IBAN address: {tracker.get_slot('recipient_iban')}")]


class ValidateRecipientName(Action):
    def name(self) -> str:
        return "validate_recipient_name"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> List[EventType]:
        recipient_name = tracker.get_slot("recipient_name")
        found_recipient = None
        for recipient in all_recipients:
            if recipient.get("name") == recipient_name:
                found_recipient = recipient
                break
        events = [SlotSet("is_existing_recipient", True if found_recipient else False), SlotSet("recipient_name", recipient_name)]
        if found_recipient:
            events.append(SlotSet("recipient_iban", found_recipient.get("iban")))
            events.append(SlotSet("recipient_phone_number", found_recipient.get("phone_number")))
        else:
            events.append(SlotSet("recipient_iban", None))
            events.append(SlotSet("recipient_phone_number", None))

        return events
