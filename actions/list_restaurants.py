import random
from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_restaurants


class ListRestaurants(Action):

    def name(self) -> str:
        return "action_list_restaurants"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[str, Any]
    ):
        restaurants = get_restaurants(tracker.sender_id)

        if len(restaurants) > 0:
            restaurants = random.sample(restaurants, 5)
            sorted_data = sorted(restaurants, key=lambda r: (r.cuisine, r.city))
            restaurants_list = "\n".join([
                f"- {r.name}, {r.address} ({r.cuisine})"for r in sorted_data
            ])

            dispatcher.utter_message(
                f"Here are some restaurants in Berlin:\n{restaurants_list}"
            )
        else:
            dispatcher.utter_message(
                "I'm sorry. I'm unable to find any restaurants at the moment."
            )