from typing import List

import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import SharedContext
from actions.shared_context_events import (
    CreditCardPayment,
    Currency,
    TravelBooked,
    common_event_field_values,
)

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
        # user_id = tracker.sender_id

        SharedContext.store(
            TravelBooked(
                destination="Berlin",
                start_date="2025-10-01T10:00:00+00:00",
                end_date="2025-10-10T18:00:00+00:00",
                payment=CreditCardPayment(
                    card_number="1234 5678 9012 3456",
                    amount=Currency(
                        code="USD",
                        amount=500.0,
                    ),
                ),
                **common_event_field_values(),
            )
        )
        return []
