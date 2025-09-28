from typing import Any, Dict

import structlog
from pydantic import BaseModel
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import (
    QueryInput,
    SharedContext,
    SingleQueryInput,
    find_blocked_card,
)
from actions.shared_context_events import CreditCardUnblocked

logger = structlog.get_logger(__name__)


class UnblockedCreditCardNote(BaseModel):
    credit_card: str
    operation: str


class UnblockCard(Action):
    def name(self) -> str:
        return "unblock_card"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ):
        blocked_card_number = tracker.get_slot("blocked_card")

        query = QueryInput(
            queries=[
                SingleQueryInput(
                    additional_filters={
                        "user_id": "user123",
                        "type": "credit_card_blocked",
                        "card.card_number": blocked_card_number,
                    }
                )
            ],
            count=1,
        )

        logger.debug("unblock_card.query", query_input=query.model_dump(mode="json"))

        blocked_cards = SharedContext.get(query)

        blocked_card_event = find_blocked_card(blocked_cards)

        logger.debug(
            "unblock_card.blocked_card_event",
            blocked_card_event=blocked_card_event.model_dump_json()
            if blocked_card_event
            else None,
        )

        if not blocked_card_event:
            dispatcher.utter_message(
                "Sorry, the card in question is not blocked or does not exist."
            )
            return [SlotSet("unblock_card_result", "failed")]

        try:
            SharedContext.store(
                CreditCardUnblocked(
                    user_id="user123",
                    card=blocked_card_event.card,
                    timestamp="2024-10-01T10:00:00+00:00",
                    source="Rasa",
                    reason="Credit card unblocked because it was a mistake",
                )
            )
        except Exception as e:
            return [SlotSet("unblock_card_result", "failed")]

        return [SlotSet("unblock_card_result", "success")]
