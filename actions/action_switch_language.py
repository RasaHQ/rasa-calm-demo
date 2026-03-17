from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher


class ActionSwitchLanguage(Action):
    def name(self) -> str:
        return "action_switch_language"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        switch_language = tracker.get_slot("switch_language")
        return [
            SlotSet("language", switch_language),
        ]
