from typing import Dict, Optional, Text, cast

import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import QueryInput, SharedContext, SingleQueryInput
from actions.shared_context_events import CreditCardUnblocked, EventsList

logger = structlog.get_logger(__name__)


class FetchLastUnblockedCard(Action):
    def name(self) -> Text:
        return "fetch_last_unblocked_card"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # Call localhost:8000/query with Query object

        events = SharedContext.get(
            QueryInput(
                queries=[
                    SingleQueryInput(
                        additional_filters={
                            "user_id": tracker.sender_id,
                            "type": {
                                "$in": ["credit_card_blocked", "credit_card_unblocked"]
                            },
                        }
                    )
                ],
                count=1,
            )
        )

        unblocked_card_event = self._find_last_unblocked_card(events)

        if unblocked_card_event:
            logger.info(
                "fetch_last_unblocked_card.unblocked_card_found",
                message="Last unblocked card found in shared context",
                event_info=unblocked_card_event.model_dump_json(),
            )
            return [
                SlotSet("last_unblocked_card", unblocked_card_event.card.card_number),
                SlotSet("card_for_payment", unblocked_card_event.card.card_number),
            ]
        logger.debug("fetch_last_unblocked_card.no_unblocked_card_found")
        return [SlotSet("last_unblocked_card", ""), SlotSet("card_for_payment", "")]

    @staticmethod
    def _find_last_unblocked_card(events: EventsList) -> Optional[CreditCardUnblocked]:
        # Start from the end of the list and look for the first Credit Card blocked event
        # Events are assumed to be in descending order by timestamp
        for event in events:
            if event.type == "credit_card_blocked":
                # Check if there's a corresponding Credit Card unblocked event after this
                started_event = event
                for subsequent_event in events[: events.index(started_event)]:
                    if subsequent_event.type == "credit_card_unblocked":
                        return cast(
                            CreditCardUnblocked, subsequent_event
                        )  # Found a matching Credit Card unblocked event, so no unfinished flow
                # If we reach here, it means there's no matching Unblocked Card event
        return None  # No Credit Card unblocked event found
