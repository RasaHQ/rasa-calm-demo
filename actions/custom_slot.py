from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ActionCustomSlot(Action):

    def name(self) -> str:
        return "action_custom_slot"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: dict) -> list:
        logger.info("Executing action_custom_slot")
        timenow = datetime.now().strftime("%H:%M:%S")
        return [SlotSet("another_slot", f"{timenow}")]
