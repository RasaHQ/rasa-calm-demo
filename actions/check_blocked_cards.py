from typing import Dict, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    QueryInput,
    RecentEventsInput,
    SharedContext,
    SingleQueryInput,
    find_blocked_card,
)


class CheckBlockedCards(Action):
    def name(self) -> Text:
        return "check_blocked_cards"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # Call localhost:8000/query with Query object

        # user_id = tracker.sender_id

        # events = SharedContext.get(
        #     QueryInput(
        #         queries=[
        #             SingleQueryInput(
        #                 additional_filters={
        #                     "user_id": "user123",
        #                     "type": {
        #                         "$in": ["credit_card_blocked", "credit_card_unblocked"]
        #                     },
        #                 }
        #             )
        #         ],
        #         count=1,
        #     )
        # )

        events = SharedContext.get_recent_events(
            RecentEventsInput(
                count=10,
                types=["credit_card_blocked", "credit_card_unblocked"],
                user_id=user_id,
            )
        )

        blocked_card_event = find_blocked_card(events)

        if blocked_card_event:
            message = f"Your latest blocked card is {blocked_card_event.card.card_number} due to {blocked_card_event.reason}."
            dispatcher.utter_message(message)
            return [SlotSet("blocked_card", blocked_card_event.card.card_number)]

        dispatcher.utter_message("Sorry, ATM I couldn't retrieve your blocked cards.")
        return [SlotSet("blocked_card", "")]
