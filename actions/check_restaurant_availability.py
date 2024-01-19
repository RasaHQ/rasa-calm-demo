from datetime import datetime, timedelta

from rasa.shared.nlu.training_data.message import Message
from rasa_sdk.interfaces import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa.nlu.extractors.duckling_entity_extractor import DucklingEntityExtractor
from typing import List, Optional

duckling_config = {**DucklingEntityExtractor.get_default_config(),
                   "url": "https://rasa:xCTBjGqjTqDqE6X72FXLiBWVXYaQDZ@duckling.rasa-dev.io",
                   "dimensions": ["time"]}
duckling = DucklingEntityExtractor(duckling_config)


class CheckRestaurantAvailability(Action):

    def name(self) -> str:
        return "check_restaurant_availability"

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

        def parse_datetime(text: str) -> Optional[datetime]:
            msg = Message.build(text)
            duckling.process([msg])
            if len(msg.data["entities"]) == 0:
                return None
            parsed_value = msg.data["entities"][0]["value"]
            if isinstance(parsed_value, dict):
                parsed_value = parsed_value["from"]
            return datetime.fromisoformat(parsed_value)

        def is_restaurant_available(date: datetime) -> bool:
            # monday to thursday available after 7pm
            if date.weekday() < 4:
                return date.hour > 19
            # Friday to Sunday available 4-5pm and 8-10pm
            else:
                return 16 <= date.hour <= 17 or 20 <= date.hour <= 22

        def get_alternative_restaurant() -> str:
            return "Prometheus Pizza"

        def alternative_date_to_string(original_date: datetime,
                                       alternative_date: datetime) -> str:
            fmt = "%I%p"
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            if today.day == alternative_date.day:
                fmt = "today " + fmt
            elif tomorrow.day == alternative_date.day:
                fmt = "tomorrow " + fmt
            else:
                fmt = "%A " + fmt
            return alternative_date.strftime(fmt).replace("0", "")

        def find_alternative_date(
                original_date: datetime,
                previously_offered_alternatives: List[str]
        ) -> Optional[str]:
            deltas = [timedelta(hours=-1), timedelta(hours=1), timedelta(hours=2),
                      timedelta(days=1), timedelta(days=2)]
            date_with_deltas = [original_date + delta for delta in deltas]
            available_dates = [alternative_date
                               for alternative_date in date_with_deltas
                               if is_restaurant_available(alternative_date)]
            available_dates_str = [alternative_date_to_string(original_date,
                                                              available_date)
                                   for available_date in available_dates]
            not_offered_before = [available_date
                                  for available_date in available_dates_str
                                  if available_date not in
                                  previously_offered_alternatives]
            if len(not_offered_before) > 0:
                return not_offered_before[0]
            else:
                return None

        restaurant_name = tracker.slots.get("book_restaurant_name_of_restaurant")
        number_of_people = tracker.slots.get("book_restaurant_number_of_people")
        is_date_flexible = tracker.slots.get("book_restaurant_is_date_flexible")
        booking_time = parse_datetime(tracker.slots.get("book_restaurant_time"))
        booking_date = parse_datetime(tracker.slots.get("book_restaurant_date"))
        previously_offered_alternatives = \
            tracker.slots.get("book_restaurant_offered_alternative_dates")
        date = datetime.combine(booking_date.date(), booking_time.time())

        if is_restaurant_available(date) or \
                restaurant_name == get_alternative_restaurant():
            return [SlotSet("is_restaurant_available", True)]
        alternative_time = find_alternative_date(date,
                                                 previously_offered_alternatives)
        if is_date_flexible and is_date_flexible != "False" \
                and alternative_time is not None:
            alternative = alternative_time
            previously_offered_alternatives.append(alternative)
            has_alternative_restaurant = False
        else:
            alternative = get_alternative_restaurant()
            has_alternative_restaurant = True

        return [
            SlotSet("is_restaurant_available", False),
            SlotSet("book_restaurant_given_alternative", alternative),
            SlotSet("book_restaurant_has_alternative_restaurant",
                    has_alternative_restaurant),
            SlotSet("book_restaurant_offered_alternative_dates",
                    previously_offered_alternatives)
        ]
