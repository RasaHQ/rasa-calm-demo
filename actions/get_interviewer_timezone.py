import logging
from typing import Any

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.services import get_hiring_process_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionGetInterviewerTimezone(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_get_interviewer_timezone"

    @module_monitor("schedule_interview", "action_get_interviewer_timezone")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metadata = get_user_metadata(tracker)
        logger.debug(f"action get interviewer timezone: metadata {metadata}")
        context = get_context(metadata)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []
        job_id = tracker.get_slot("job_id")
        hiring_process_service = get_hiring_process_service()
        interviewer_id = await hiring_process_service.get_interviewer_id(
            # TODO: replace it with proper conversation ctx solution
            interviewer_external_id=context.x_caller_identity.external_id,
            job_id=job_id,
            context=context,
        )
        if interviewer_id:
            timezone = await hiring_process_service.get_interviewer_timezone(interviewer_id, context)
            if timezone:
                return [
                    SlotSet("interviewer_timezone", timezone),
                    SlotSet("interviewer_id", interviewer_id),
                ]
            else:
                logger.warning("No valid timezone found")
        else:
            # TODO: we should handle this case in a better way
            logger.warning("No interviewer id found")
        return []
