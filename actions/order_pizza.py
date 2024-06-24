from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher


class AskPizzaConfirmationOrder(Action):

    def name(self) -> str:
        return "action_ask_confirmation_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        dispatcher.utter_message(
            response="utter_confirm",
            buttons=[
                {"title": "Yes", "payload": "/SetSlots(confirmation_order=True)"},
                {"title": "No", "payload": "/SetSlots(confirmation_order=False)"}
            ]
        )
        return []


class ActionCheckMembershipPoints(Action):

    def name(self) -> str:
        return "action_check_points"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        dispatcher.utter_message(
            text="You have 150 points in your membership account. That's enough to get a free pizza!"
        )
        return [SlotSet("membership_points", 150)]


class ActionCorrectOrderDetails(Action):

    def name(self) -> str:
        return "action_ask_correct_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        dispatcher.utter_message(
            text="I'm sorry about that. Let's correct your order. What would you like to change?",
            buttons=[
                {"title": "Pizza", "payload": "/SetSlots(pizza=null)"},
                {"title": "Quantity", "payload": "/SetSlots(num_pizza=null)"},
                {"title": "Address", "payload": "/SetSlots(address=null)"},
            ]
        )
        return [SlotSet("confirmation_order", None), SlotSet("correct_order", True)]

class ActionShowVacancie(Action):

    def name(self) -> str:
        return "action_show_vacancies"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        department = tracker.get_slot("department")

        if department == "kitchen":
            dispatcher.utter_message(
                text="We are looking for a chef and a kitchen assistant. Please visit our website to apply."
            )
        elif department == "service":
            dispatcher.utter_message(
                text="We are looking for a cashier and a waiter. Please visit our website to apply."
            )
        else:
            dispatcher.utter_message(
                text="We don't have any vacancies at the moment in that department. Please check back later."
            )
        return []
