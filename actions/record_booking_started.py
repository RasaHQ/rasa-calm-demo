from typing import Any, Dict

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    RecentEventsInput,
    SharedContext,
    find_unfinished_travel_booking,
)
from actions.shared_context_events import (
    TravelBookingStarted,
    common_event_field_values,
)


class RecordBookingStarted(Action):
    def name(self) -> str:
        return "record_booking_started"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ):
        # user_id = tracker.sender_id

        events = SharedContext.get_recent_events(
            RecentEventsInput(
                count=10,
                types=["travel_booking_started", "travel_booked"],
                user_id=user_id,
            )
        )

        unfinished_travel_booking = find_unfinished_travel_booking(events)

        if not unfinished_travel_booking:
            SharedContext.store(
                TravelBookingStarted(
                    destination="Berlin",  # TODO: get from slot
                    start_date="2026-12-20T10:00:00Z",  # TODO: get from slot
                    end_date="2026-12-30T10:00:00Z",  # TODO: get from slot
                    **common_event_field_values(),
                )
            )
        return []
