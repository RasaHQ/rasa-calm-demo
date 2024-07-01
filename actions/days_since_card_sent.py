import random
from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_restaurants
from rasa_sdk.events import SlotSet


class DaysSinceCardSent(Action):
    """This action sets the replace_card_eligibility slot to a random value within the list of possible values."""

    def __init__(self):
        # Define the name of the action
        self.index = 0
        self.replace_card_eligibility_values = ["is_eligible", "no_card_on_file", "not_eligible_child"]


    def name(self) -> str:
        return "action_days_since_card_sent"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]
    ):
        # Generate random number between 1 and 14
        days = random.randint(1, 14)
        print(f"Setting days_since_card_sent slot to {days}")
        # Set the replace_card_eligibility slot to a random value from the list
        return [SlotSet("days_since_card_sent", days)]
