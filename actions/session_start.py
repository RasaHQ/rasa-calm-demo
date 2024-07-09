import logging
from typing import Dict, Text, Any, List, Optional
from rasa_sdk.types import DomainDict
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher, Action
from importlib.metadata import version
import random
import os
from pydantic import BaseModel, HttpUrl, UUID4

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


def get_cards(num_cards: int) -> List[Any]:
    available_cards = []
    return random.sample(available_cards, num_cards)


def select_cardholder_profile():
    cardholder_profiles = [
        {
            "name": "Maria Gonzalez",
            "replacement_eligibility": "is_eligible",
            "address_line_1": "300 Lakeside Ave",
            "address_line_2": "Unit 121",
            "city": "Seattle",
            "state": "WA",
            "postal_code": "98112",
            "country": "US",
            "cards": [
                {"name": "Gold Card", "number": "xxxx1"},
                {"name": "Satin Card", "number": "xxxx3"},
            ],
        },
        {
            "name": "Stefan Müller",
            "replacement_eligibility": "is_eligible",
            "address_line_1": "Laemmleshalde 33",
            "address_line_2": "",
            "city": "Herrenberg",
            "state": "BV",
            "postal_code": "71083",
            "country": "DE",
            "cards": [
                {"name": "Silicon Card", "number": "xxxx1"},
                {"name": "Family Card", "number": "xxxx4"},
            ],
        },
        {
            "name": "Mira Patel",
            "replacement_eligibility": "is_eligible",
            "address_line_1": "4 Church Walk",
            "address_line_2": "",
            "city": "Richmond",
            "state": "Surrey",
            "postal_code": "TW9 1SN",
            "country": "UK",
            "cards": [
                {"name": "Gold Card", "number": "xxxx1"},
                {"name": "Kids Card", "number": "xxxx2"},
                {"name": "Family Card", "number": "xxxx4"},
            ],
        },
        {
            "name": "David Benoit",
            "replacement_eligibility": "not_eligible_child",
            "address_line_1": "7 Rue de la Coudre",
            "address_line_2": "",
            "city": "Saint-Malo",
            "state": "Bretagne",
            "postal_code": "35400",
            "country": "FR",
            "cards": [
                {"name": "Kids Card", "number": "xxxx2"},
            ],
        },
    ]
    # select a random cardholder profile
    profile = random.choice(cardholder_profiles)
    return profile


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
        events = []
        # the session should begin with a `session_started` event
        events.append(SessionStarted())

        # select cardholder profile
        profile = select_cardholder_profile()

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
            f"Setting current_card_name slot to {cards[0]['name']}, current_card_number slot to {cards[0]['number']}, cardholder_replacement_eligibility slot to {profile['replacement_eligibility']}"
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
