from typing import Dict, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Action

from actions.db import get_restaurants


class AskForRestaurantFormCuisine(Action):
    def name(self) -> Text:
        return "action_ask_restaurant_form_cuisine"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ):
        restaurants = get_restaurants(tracker.sender_id)
        cuisine_list = set([
            r.cuisine
            for r in restaurants
            if r.city.lower() == tracker.get_slot("city").lower()
        ])

        dispatcher.utter_message(
            text="What cuisine are you looking for?",
            buttons=[
                {"title": c, "payload": f'/inform{{"cuisine":"{c}"}}'}
                for c in cuisine_list
            ]
        )


class AskForRestaurantFormRestaurantName(Action):
    def name(self) -> Text:
        return "action_ask_restaurant_form_restaurant_name"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ):
        restaurants = get_restaurants(tracker.sender_id)

        restaurant_names = set([
            r.name for r in restaurants
            if r.city.lower() == tracker.get_slot("city").lower() and
            r.cuisine.lower() == tracker.get_slot("cuisine").lower()
        ])

        if len(restaurant_names) > 0:
            dispatcher.utter_message(
                text="Do you know which restaurant you would like me to reverse a table at?",
                buttons=[
                    {"title": r, "payload": f'/inform{{"restaurant_name":"{r}"}}'}
                    for r in restaurant_names
                ]
            )
        else:
            dispatcher.utter_message("I'm sorry I could not find any suitable restaurant "
                                     "for you.")
