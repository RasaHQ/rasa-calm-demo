from rasa_sdk.interfaces import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import List


class SearchHotelAction(Action):
    def name(self) -> str:
        return "action_search_hotel"

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> List[EventType]:
        """Execute the side effects of this action.

        Args:
            dispatcher: the dispatcher which is used to
                send messages back to the user. Use
                `dispatcher.utter_message()` for sending messages.
            tracker: the state tracker for the current
                user. You can access slot values using
                `tracker.get_slot(slot_name)`, the most recent user message
                is `tracker.latest_message.text` and any other
                `rasa_sdk.Tracker` property.
            domain: the bot's domain
        Returns:
            A dictionary of `rasa_sdk.events.Event` instances that is
                returned through the endpoint
        """

        return [SlotSet("hotel_name", "Shadyside Inn"), SlotSet("hotel_average_rating", 2)]
