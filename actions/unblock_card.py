from typing import Any, Dict

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.db import Contact, add_contact, get_contacts


class UnblockCard(Action):
    def name(self) -> str:
        return "unblock_card"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ):
        blocked_card = tracker.get_slot("blocked_card")
        dispatcher.utter_message(
            f"Your card {blocked_card} has been unblocked. You can now use it for transactions."
        )
        return [SlotSet("return_value", "success")]
