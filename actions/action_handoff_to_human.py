from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import SharedContext
from actions.shared_context_events import (
    HumanHandoffRequested,
    common_event_field_values,
)


class ActionHandoffToHuman(Action):
    def name(self) -> str:
        return "action_handoff_to_human"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        SharedContext.store(
            HumanHandoffRequested(
                **common_event_field_values(),
                reason="User requested to speak to a human agent",
                tags=["rasa", "handoff", "human_agent"],
                current_state=tracker.current_state(),
            )
        )

        return []
