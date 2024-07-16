import logging
from typing import Dict, Text, Any, List, Optional
from rasa_sdk.types import DomainDict
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher, Action
from importlib.metadata import version
import random
import os
from pydantic import BaseModel, HttpUrl, UUID4
from actions.api.mock_bank_api import BankAPI

__version__ = "0.1.0"
__build_date__ = "1 Jul 2024"


class Card(BaseModel):
    name: str
    number: str
    replacement_eligibility: str


# from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import (
    AllSlotsReset,
    SlotSet,
    EventType,
    ActionExecuted,
    SessionStarted,
    FollowupAction,
)

logger = logging.getLogger(__name__)


class ActionSessionStart(Action):
    """Executes at start of session"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_session_start"

    @staticmethod
    def _slot_set_events_from_tracker(
        tracker: "Tracker",
    ) -> List["SlotSet"]:
        """Fetches SlotSet events from tracker and carries over keys and values"""

        # when restarting most slots should be reset, except for the these
        relevant_slots = []

        return [
            SlotSet(
                key=event.get("name"),
                value=event.get("value"),
            )
            for event in tracker.events
            if event.get("event") == "slot" and event.get("name") in relevant_slots
        ]

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        metadata = tracker.get_slot("session_started_metadata")
        events = []
        # the session should begin with a `session_started` event
        events.append(SessionStarted())

        bank_api = BankAPI()

        # select a cardholder profile
        profile = bank_api.select_random_cardholder_profile()

        num_cards = len(profile["cards"])
        print(f"Setting num_cards slot to {num_cards}")
        events.append(SlotSet("num_cards", num_cards))

        cards = profile["cards"]
        events.append(SlotSet("cards", cards))
        events.append(SlotSet("current_card_name", cards[0]["name"]))
        events.append(SlotSet("current_card_number", cards[0]["number"]))
        events.append(
            SlotSet(
                "cardholder_replacement_eligibility",
                profile["replacement_eligibility"],
            )
        )
        logger.debug(
            f"Using profile for {profile['name']}, current_card_name slot to {cards[0]['name']}, current_card_number slot to {cards[0]['number']}, cardholder_replacement_eligibility slot to {profile['replacement_eligibility']}"
        )

        events.append(SlotSet("cardholder_name", profile["name"]))
        events.append(SlotSet("address_line_1", profile["address_line_1"]))
        events.append(SlotSet("address_line_2", profile["address_line_2"]))
        events.append(SlotSet("city", profile["city"]))
        events.append(SlotSet("state", profile["state"]))
        events.append(SlotSet("postal_code", profile["postal_code"]))
        events.append(SlotSet("country", profile["country"]))

        events.append(ActionExecuted("action_listen"))
        return events
