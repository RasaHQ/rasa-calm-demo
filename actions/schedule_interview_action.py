import ast
import logging
from typing import Any

from rasa_sdk import Tracker
from sa_commons_monitoring import module_monitor

from app.constants import OTHER
from app.context import get_context, get_user_metadata
from app.sr_core.services import get_self_scheduling_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionScheduleInterview(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_schedule_interview"

    @module_monitor("schedule_interview", "action_schedule_interview")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metadata = get_user_metadata(tracker)
        logger.debug(f"action schedule interview: metadata {metadata}")
        context = get_context(metadata)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []
        self_scheduling_service = get_self_scheduling_service()
        start_end_times = ast.literal_eval(tracker.get_slot("corrected_interviewer_availability_utc"))
        interview_type = tracker.get_slot("interview_type")
        selected_candidate_positions = ast.literal_eval(
            tracker.get_slot("selected_candidates_positions").replace(";", ",")
        )
        candidate_ids = tracker.get_slot("retrieved_candidates_ids")
        selected_candidates_ids = [candidate_ids[int(i) - 1] for i in selected_candidate_positions]
        interview_duration_choices = tracker.get_slot("interview_duration")
        interview_duration_custom = tracker.get_slot("custom_interview_duration")
        interviewer_id = tracker.get_slot("interviewer_id")
        location = tracker.get_slot("location")
        email_subject = tracker.get_slot("email_subject")
        email_content = tracker.get_slot("email_body")
        timezone = tracker.get_slot("interviewer_timezone")
        interview_duration = (
            interview_duration_choices if interview_duration_choices != OTHER else interview_duration_custom
        )
        try:
            await self_scheduling_service.send_self_scheduling_request(
                start_end_times=start_end_times,
                duration=interview_duration,
                interview_type=interview_type,  # to be discussed with product and design
                application_uuids=selected_candidates_ids,
                interviewers_ids=[interviewer_id],
                location_type="ONSITE",  # to be discussed with product and design
                location=location,
                event_title="interview",  # to be discussed with product and design
                hiring_stage="interview",  # to be discussed with product and design
                private_interview=True,  # to be discussed with product and design
                email_subject=email_subject,
                email_content=email_content,
                timezone=timezone,
                capacity=1,  # to be discussed with product and design
                context=context,
            )
            dispatcher.send_text_message(
                text="Self-scheduling email has been successfully sent.\nInterviews should be scheduled soon."
            )
            return []
        except Exception as e:
            logger.warning(f"An error occurred while calling the self-scheduling API: {e}")
            dispatcher.send_text_message(
                text="Self-scheduling email has not been successfully sent.\nPlease try again."
            )
            return []
