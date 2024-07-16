import random
import logging
from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_restaurants
from rasa_sdk.events import SlotSet
from actions.api.mock_bank_api import BankAPI

logger = logging.getLogger(__name__)

bank_api = BankAPI()

class DaysSinceCardSent(Action):
    """This action sets the replace_card_eligibility slot to a random value within the list of possible values."""

    def __init__(self):
        # Define the name of the action
        self.index = 0


    def name(self) -> str:
        return "action_days_since_card_sent"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]
    ):
        cardholder_name = tracker.get_slot("cardholder_name")
        profile = bank_api.get_cardholder_by_name(cardholder_name)
        if profile:
            days = profile["days_since_card_sent"]
            logger.debug(f"Setting days_since_card_sent slot to {days}")
            return [SlotSet("days_since_card_sent", days)]

        logger.debug(f"User {cardholder_name} not found, setting days_since_card_sent slot to 100")
        return [SlotSet("days_since_card_sent", 100)]