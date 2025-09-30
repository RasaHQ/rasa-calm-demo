import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import (
    QueryInput,
    SharedContext,
    SingleQueryInput,
    find_unfinished_travel_booking,
)

logger = structlog.getLogger(__name__)


class ActionCheckForStartedFlows(Action):
    def name(self) -> str:
        return "action_check_for_started_flows"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        logger.info(
            "action_check_for_started_flows.started",
            message="Checking for unfinished flows in shared context",
        )
        user_id = tracker.sender_id
        user_id = "user123"  # TODO: remove hardcoding

        events = SharedContext.get(
            QueryInput(
                queries=[
                    SingleQueryInput(
                        additional_filters={
                            "user_id": user_id,
                            "type": {
                                "$in": ["travel_booking_started", "travel_booked"]
                            },
                        }
                    )
                ],
                count=10,
            )
        )

        unfinished_travel_booking = find_unfinished_travel_booking(events)
        if unfinished_travel_booking:
            logger.info(
                "action_check_for_started_flows.unfinished_flow_found",
                message="Unfinished flow found in shared context",
                event_info=unfinished_travel_booking.model_dump_json(),
            )
            dispatcher.utter_message(
                f"Heya, we noticed you started booking a flight "
                f"earlier to {unfinished_travel_booking.destination} "
                "Let's continue where we left off!"
            )
            return [
                SlotSet("active_flow_name", "flow_book_a_flight"),
                SlotSet("is_continued_flow", True),
            ]
            return [StartedFlowFound("book_a_flight")]
            return self.create_stack_updated_event(tracker, "book_a_flight")

        logger.info(
            "action_check_for_started_flows.no_unfinished_flow",
            message="No unfinished flow found in shared context",
        )
        return [
            SlotSet("active_flow_name", ""),
            SlotSet("is_continued_flow", False),
        ]
