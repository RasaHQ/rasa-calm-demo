from typing import Any, Dict

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    QueryInput,
    RecentEventsInput,
    SharedContext,
    SingleQueryInput,
    find_unfinished_travel_booking,
)
from actions.shared_context_events import TravelBookingStarted


class RecordBookingStarted(Action):
    def name(self) -> str:
        return "record_booking_started"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ):
        # user_id = tracker.sender_id

        # events = SharedContext.get(
        #     QueryInput(
        #         queries=[
        #             SingleQueryInput(
        #                 additional_filters={
        #                     "user_id": user_id,
        #                     "type": {
        #                         "$in": ["travel_booking_started", "travel_booked"]
        #                     },
        #                 }
        #             )
        #         ],
        #         count=10,
        #     )
        # )

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
                    user_id=user_id,
                    destination="Berlin",  # TODO: get from slot
                    start_date="2026-12-20T10:00:00Z",  # TODO: get from slot
                    end_date="2026-12-30T10:00:00Z",  # TODO: get from slot
                    source="Rasa",
                    schema_version="1.0",
                    timestamp="2025-09-01T12:00:00Z",  # TODO: use current time
                )
            )
            dispatcher.utter_message(text="Recorded the start of your travel booking.")
        return []
