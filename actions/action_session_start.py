from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
import logging

logger = logging.getLogger(__name__)

class ActionSessionStart(Action):

    def name(self) -> str:
        return "action_session_start"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        # get the metadata from the tracker
        metadata = tracker.get_slot("session_started_metadata")
        logger.info(f"🤙 action_session_start's metadata: {metadata}")

        # set appropriate slots
        if metadata:
            return [
                SlotSet("user_phone", metadata.get("user_phone")),
                SlotSet("bot_phone", metadata.get("bot_phone")),
            ]
        
        return []
