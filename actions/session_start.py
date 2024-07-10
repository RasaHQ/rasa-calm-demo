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
from rasa_sdk.events import AllSlotsReset, SlotSet, EventType, ActionExecuted, SessionStarted, FollowupAction

logger = logging.getLogger(__name__)

def get_user_profile(num_cards: int) -> List[Any]:
    
    available_cards = [
        {"name": "Gold Card", "number": "xxxx1"},
        {"name": "Kids Card", "number": "xxxx2"},
        {"name": "Satin Card", "number": "xxxx3"},
        {"name": "Family Card", "number": "xxxx4"},
    ]
    cards = random.sample(available_cards, num_cards)
    available_users = [
        {"name": "James", 
         "cards": cards, 
         "replacement_eligibility": "is_eligible",
         "address_line_1": "300 Lakeside Ave",
         "city": "Seattle",
         "state": "WA",
         "zip_code": "98112"
        },
        {"name": "Philipp", 
         "cards": cards, 
         "replacement_eligibility": "not_eligible_child",
         "address_line_1": "150 Stellar Street",
         "city": "Milwaukee",
         "state": "WI",
         "zip_code": "300212",
        },
        {"name": "Patrick", 
         "cards": cards, 
         "replacement_eligibility": "is_eligible",
         "address_line_1": "40th W Street",
         "city": "Manhattan",
         "state": "NY",
         "zip_code": "55045",
        },
        {"name": "Jason", 
         "cards": cards, 
         "replacement_eligibility": "no_card_on_file",
         "address_line_1": "30 Richmond Oaks",
         "city": "San Franscisco",
         "state": "CA",
         "zip_code": "90210",
        }
    ]
    return random.sample(available_users, 1)


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
        # the session should begin with a `session_started` event
        events = [SessionStarted()]

        num_cards = random.randint(1, 3)
        print(f"Setting num_cards slot to {num_cards}")
        events.append(SlotSet("num_cards", num_cards))

        users = get_user_profile(num_cards)[0]
        cards = users.get("cards")
        events.append(SlotSet("users", users))
        events.append(SlotSet("current_card_name", cards[0]['name']))
        events.append(SlotSet("current_card_number", cards[0]['number']))
        events.append(SlotSet("current_card_replacement_eligibility", users.get('replacement_eligibility')))
        logger.debug(f"Setting current_card_name slot to {cards[0]['name']}, current_card_number slot to {cards[0]['number']}, current_card_replacement_eligibility slot to {users['replacement_eligibility']}")

        events.append(SlotSet("address_line_1", users.get("address_line_1")))
        events.append(SlotSet("city", users.get("city")))
        events.append(SlotSet("state", users.get("state")))
        events.append(SlotSet("zip_code",users.get("zip_code")))

        events.append(ActionExecuted("action_listen"))
        return events