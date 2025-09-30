from typing import List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import QueryInput, SharedContext, SingleQueryInput
from actions.shared_context_events import TravelBooked


class CheckCreditCardFees(Action):
    def name(self) -> str:
        return "check_credit_card_fees"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> List:
        events: List[TravelBooked] = SharedContext.get(
            QueryInput(
                queries=[
                    SingleQueryInput(
                        additional_filters={
                            "user_id": "user123",
                            "type": {"$in": ["travel_booked"]},
                        }
                    )
                ],
                count=10,
            )
        )

        if not events:
            dispatcher.utter_message(
                text="Fees for your platinum card are $2 for travel bookings."
            )
            return []

        if events[0].destination.find("US") != -1:
            dispatcher.utter_message(
                text="Since you booked travel to the US, there are no fees for your platinum card."
            )

        if events[0].destination.find("Berlin") != -1:
            dispatcher.utter_message(
                text="Since you booked travel to Germany, there are no fees for your platinum card."
            )
        return []
