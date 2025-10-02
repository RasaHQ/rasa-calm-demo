import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.common import user_id
from actions.shared_context import (
    RecentEventsInput,
    SharedContext,
    find_blocked_card,
    find_finished_travel_booking,
    find_latest_unfinished_flow,
)
from actions.shared_context_events import TravelBookingStarted

logger = structlog.getLogger(__name__)


class ActionCurrentStatus(Action):
    def name(self) -> str:
        return "action_current_status"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        logger.info(
            "action_current_status.started",
            message="Checking for unfinished flows in shared context",
        )
        # user_id = tracker.sender_id

        events = SharedContext.get_recent_events(
            RecentEventsInput(
                count=10,
                types=[
                    "travel_booking_started",
                    "travel_booked",
                    "credit_card_blocked",
                    "wallet_lock_started",
                    "wallet_lock_completed",
                ],
                user_id=user_id,
            )
        )

        unfinished_flow = find_latest_unfinished_flow(events)
        if unfinished_flow:
            logger.info(
                "action_current_status.unfinished_flow_found",
                message="Unfinished flow found in shared context",
                event_info=unfinished_flow.model_dump_json(),
            )
            return [
                SlotSet("active_flow_name", unfinished_flow.flow_name()),
                SlotSet(
                    "flow_continuation_message", unfinished_flow.continuation_message()
                ),
                SlotSet("is_continued_flow", True),
            ]

        blocked_card = find_blocked_card(events)

        if (
            unfinished_flow
            and unfinished_flow.is_type(TravelBookingStarted)
            and blocked_card
        ):
            logger.info(
                "action_current_status.card_blocked_and_unfinished_traveling",
                message="Blocked card found and traveling booking unfinished in shared context",
                blocked_card=blocked_card[0].model_dump_json(),
                unfinished_travel_booking=unfinished_flow.model_dump_json(),
            )
            message = (
                f"Hi, I can see that your card ending in {blocked_card[0].card_number[-4:]} "
                f"was recently blocked. Also, you started booking a flight "
                f"to {unfinished_flow.destination} earlier. "
                "Want help?"
            )
            return [
                SlotSet("active_flow_name", unfinished_flow.flow_name()),
                SlotSet("flow_continuation_message", message),
                SlotSet("is_continued_flow", True),
            ]

        finished_travel_booking = find_finished_travel_booking(events)
        if not unfinished_flow and finished_travel_booking:
            if blocked_card:
                logger.info(
                    "action_current_status.card_blocked_and_finished_traveling",
                    message="Blocked card found and traveling booking finished in shared context",
                    blocked_card=blocked_card[0].model_dump_json(),
                    finished_travel_booking=finished_travel_booking[
                        0
                    ].model_dump_json(),
                )
                message = (
                    f"Hi, I can see that your card ending in {blocked_card[0].card_number[-4:]} "
                    f"was recently blocked. Also, you booked a flight "
                    f"to {finished_travel_booking[0].destination} earlier. "
                    "Want help?"
                )
                return [
                    SlotSet("active_flow_name", ""),
                    SlotSet("is_continued_flow", False),
                    SlotSet("custom_greet_message", message),
                ]

            logger.info(
                "action_current_status.finished_traveling",
                message="Finished traveling booking found in shared context",
                finished_travel_booking=finished_travel_booking[0].model_dump_json(),
            )

            message = (
                f"Hi, I can see that you booked a flight "
                f"to {finished_travel_booking[0].destination} earlier. "
                "Let me know if you need any help!"
            )
            return [
                SlotSet("active_flow_name", ""),
                SlotSet("is_continued_flow", False),
                SlotSet("custom_greet_message", message),
            ]

        logger.info(
            "action_current_status.no_unfinished_flow",
            message="No unfinished flow found in shared context",
        )
        return [
            SlotSet("active_flow_name", ""),
            SlotSet("is_continued_flow", False),
        ]
