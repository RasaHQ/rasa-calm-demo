from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    RecentEventsInput,
    SharedContext,
    find_finished_travel_booking,
)


class CheckUpcomingTrips(Action):
    def name(self) -> str:
        return "check_upcoming_trips"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        # user_id = tracker.sender_id

        events = SharedContext.get_recent_events(
            RecentEventsInput(
                count=10,
                types=[
                    "travel_booking_started",
                    "travel_booked",
                    "credit_card_blocked",
                ],
                user_id=user_id,
            )
        )

        booked_trip = find_finished_travel_booking(events)

        message = ""
        if booked_trip:
            message = (
                f"You have an upcoming trip to {booked_trip[0].destination}"
                f" from {booked_trip[0].start_date} to {booked_trip[0].end_date}."
                f"Do you want to load Euros to your credit card?"
            )
        return [SlotSet("upcoming_trips", message)]
