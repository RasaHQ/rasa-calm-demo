from typing import List

import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, StartedFlowFound
from rasa_sdk.executor import CollectingDispatcher

from rasa.core.shared_context.events import CreditCardPayment, Currency, TravelBooked
from rasa.core.shared_context.shared_context import SharedContext

logger = structlog.getLogger(__name__)


class ActionBookFlightCompleted(Action):
    def name(self) -> str:
        return "action_book_flight_completed"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> List:
        logger.info(
            "action_book_flight_completed.started",
            message="Checking for unfinished flows in shared context",
        )
        user_id = tracker.sender_id
        user_id = "user123"  # TODO: remove hardcoding

        SharedContext.store(
            TravelBooked(
                user_id=user_id,
                destination="Berlin",
                start_date="2025-10-01T10:00:00+00:00",
                end_date="2025-10-10T18:00:00+00:00",
                timestamp="2025-09-24T15:20:00+00:00",
                source="Rasa",
                payment=CreditCardPayment(
                    card_number="1234 5678 9012 3456",
                    amount=Currency(
                        code="USD",
                        amount=500.0,
                    ),
                ),
            )
        )
        return []
