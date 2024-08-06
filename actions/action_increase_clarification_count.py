from rasa_sdk.events import SlotSet
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ActionIncreaseClarificationCount(Action):
    """Action which clarifies which flow to start."""

    def name(self) -> str:
        """Return the flow name."""
        return "action_increase_clarification_count"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict
    ) -> list:
        attempts = tracker.get_slot("clarification_count")
        if not attempts:
            attempts = 0

        return [SlotSet("clarification_count", attempts + 1)]
