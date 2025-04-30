import logging
from typing import Any

from rasa_sdk import Tracker
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.services import get_hiring_process_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import Button, SingleChoicePayload

logger = logging.getLogger(__name__)


class ActionAskInterviewType(BaseAction[SingleChoicePayload]):
    def name(self) -> str:
        return "action_ask_interview_type"

    @module_monitor("schedule_interview", "action_ask_interview_type")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[SingleChoicePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        metadata = get_user_metadata(tracker)
        logger.debug(f"action ask interview type: metadata {metadata}")
        context = get_context(metadata)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []

        hiring_process_service = get_hiring_process_service()
        interview_types = await hiring_process_service.retrieve_interview_types(context)

        dispatcher.send_template_message(
            template="utter_ask_interview_type_message",
            payload=SingleChoicePayload(
                options=[
                    Button(
                        title=int_type,
                        payload=f"/SetSlots(interview_type={int_type})",
                    )
                    for int_type in interview_types
                ]
            ),
        )
        return events
