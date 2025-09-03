from typing import Dict, Optional, Text

import requests
from pydantic import BaseModel
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from rasa.shared.core.events import SlotSet


class BlockedCreditCardDetails(BaseModel):
    attempts: int
    locations: list[str]
    timestamps: list[str]


class BlockedCreditCardNote(BaseModel):
    credit_card: str
    operation: str
    reason: str
    details: Optional[BlockedCreditCardDetails] = None


class CheckBlockedCards(Action):
    def name(self) -> Text:
        return "check_blocked_cards"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # Call localhost:8000/query with Query object
        response = requests.post(
            "http://localhost:8000/query",
            json={
                "user_id": "user_12345",
                "query_text": "Get latest blocked card.",
                "memory_source": "all",
            },
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            blocked_card_info = response.json()
            card = BlockedCreditCardNote(**blocked_card_info)
            message = (
                f"Your latest blocked card is {card.credit_card} due to {card.reason}."
            )
            dispatcher.utter_message(message)
            return [SlotSet("blocked_card", card.credit_card)]

        else:
            dispatcher.utter_message(
                "Sorry, ATM I couldn't retrieve your blocked cards."
            )
            return [SlotSet("blocked_card", None)]
