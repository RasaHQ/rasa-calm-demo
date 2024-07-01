import random
from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_restaurants
from rasa_sdk.events import SlotSet


class ReplaceCardElibigility(Action):
    """This action sets the replace_card_eligibility slot to a random value within the list of possible values."""

    def __init__(self):
        # Define the name of the action
        self.index = 0
        self.replace_card_eligibility_values = ["is_eligible", "no_card_on_file", "not_eligible_child"]


    def name(self) -> str:
        return "action_replace_card_eligibility"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]
    ):
        # List of possible values for the replace_card_eligibility slot
        value = self.replace_card_eligibility_values[self.index]
        self.index += 1
        if self.index >= len(self.replace_card_eligibility_values):
            self.index = 0

        print(f"Setting replace_card_eligibility slot to {value}")
        # Set the replace_card_eligibility slot to a random value from the list
        return [SlotSet("replace_card_eligibility", value)]
