from typing import List, Optional

import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, StartedFlowFound
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import QueryInput, SharedContext, SingleQueryInput
from actions.shared_context_events import Event, EventsList

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

        unfinished_flow_event = self.find_unfinished_flow(events)
        if unfinished_flow_event:
            logger.info(
                "action_check_for_started_flows.unfinished_flow_found",
                message="Unfinished flow found in shared context",
                event_info=unfinished_flow_event.model_dump_json(),
            )
            dispatcher.utter_message(
                f"Heya, we noticed you started booking a flight "
                f"earlier to {unfinished_flow_event.destination} "
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

    @staticmethod
    def find_unfinished_flow(events: EventsList) -> Optional[Event]:
        # Start from the end of the list and look for the first TravelBookingStarted event
        # Events are assumed to be in descending order by timestamp
        for event in events:
            if event.type == "travel_booking_started":
                # Check if there's a corresponding TravelBooked event after this
                started_event = event
                for subsequent_event in events[: events.index(started_event)]:
                    if subsequent_event.type == "travel_booked":
                        return None  # Found a matching TravelBooked event, so no unfinished flow
                # If we reach here, it means there's no matching TravelBooked event
                return started_event
        return None  # No TravelBookingStarted event found
