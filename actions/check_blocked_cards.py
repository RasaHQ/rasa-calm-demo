from typing import Dict, Optional, Text, cast

import requests
from pydantic import BaseModel
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    QueryInput,
    SharedContext,
    SingleQueryInput,
    find_blocked_card,
)
from actions.shared_context_events import CreditCardBlocked, EventsList


class CheckBlockedCards(Action):
    def name(self) -> Text:
        return "check_blocked_cards"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # Call localhost:8000/query with Query object

        events = SharedContext.get(
            QueryInput(
                queries=[
                    SingleQueryInput(
                        additional_filters={
                            "user_id": "user123",
                            "type": {
                                "$in": ["credit_card_blocked", "credit_card_unblocked"]
                            },
                        }
                    )
                ],
                count=1,
            )
        )

        blocked_card_event = find_blocked_card(events)

        if blocked_card_event:
            message = f"Your latest blocked card is {blocked_card_event.card.card_number} due to {blocked_card_event.reason}."
            dispatcher.utter_message(message)
            return [SlotSet("blocked_card", blocked_card_event.card.card_number)]

        dispatcher.utter_message("Sorry, ATM I couldn't retrieve your blocked cards.")
        return [SlotSet("blocked_card", "")]
