import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    RecentEventsInput,
    SharedContext,
    find_latest_unfinished_flow,
)

logger = structlog.getLogger(__name__)

event_to_flow_mapping = {
    "travel_booking_started": "flow_book_a_flight",
    "wallet_lock_started": "flow_lost_wallet",
}


class ActionCheckForStartedFlows(Action):
    def name(self) -> str:
        return "check_for_started_flows"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        logger.info(
            "check_for_started_flows.started",
            message="Checking for unfinished flows in shared context",
        )
        # user_id = tracker.sender_id

        events = SharedContext.get_recent_events(
            RecentEventsInput(
                count=10,
                types=["travel_booking_started", "travel_booked"],
                user_id=user_id,
            )
        )

        started_flow_event = find_latest_unfinished_flow(events)

        if not started_flow_event:
            logger.info(
                "check_for_started_flows.no_unfinished_flow",
                message="No unfinished flow found in shared context",
            )
            return [
                SlotSet("active_flow_name", ""),
                SlotSet("is_continued_flow", False),
            ]

        flow_name = started_flow_event.flow_name()
        message = started_flow_event.continuation_message()

        logger.info(
            "check_for_started_flows.unfinished_flow_found",
            message="Unfinished flow found in shared context",
            event_info=started_flow_event.model_dump_json(),
        )

        return [
            SlotSet("active_flow_name", flow_name),
            SlotSet("is_continued_flow", True),
            SlotSet("flow_continuation_message", message),
        ]
