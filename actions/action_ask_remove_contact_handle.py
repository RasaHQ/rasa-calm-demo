from typing import Dict, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Action

from actions.db import get_contacts


class AskForRemoveContactHandle(Action):
    def name(self) -> Text:
        return "action_ask_remove_contact_handle"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ):
        contacts = get_contacts(tracker.sender_id)

        dispatcher.utter_message(
            text="What's the handle of the user you want to remove?",
            buttons=[
                {"title": f"{c.handle} ({c.name})", "payload": c.handle}
                for c in contacts
            ]
        )
