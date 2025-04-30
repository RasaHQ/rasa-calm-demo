import logging
from typing import Any

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import BasePayload
from .ask_schedule_interview_job_index import ScheduleInterviewJobsTypeAdapter

logger = logging.getLogger(__name__)


RESET_SELECTED_JOB_EVENTS = [
    SlotSet("schedule_interview_job_index", None),
    SlotSet("schedule_interview_found_jobs", None),
    SlotSet("schedule_interview_found_job_count", None),
]


class ValidateScheduleInterviewJobIndex(BaseAction[BasePayload]):
    def name(self) -> str:
        return "validate_schedule_interview_job_index"

    @module_monitor("schedule_interview", "validate_schedule_interview_job_index")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[BasePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        logger.debug("Validating schedule_interview_job_index")

        schedule_interview_found_jobs = tracker.get_slot("schedule_interview_found_jobs")
        if schedule_interview_found_jobs is None:
            logger.warning("Slot schedule_interview_found_jobs is None")
            return RESET_SELECTED_JOB_EVENTS

        try:
            jobs = ScheduleInterviewJobsTypeAdapter.validate_python(schedule_interview_found_jobs)
        except ValueError:
            logger.warning("Slot schedule_interview_found_jobs cannot be parsed")
            return RESET_SELECTED_JOB_EVENTS

        schedule_interview_job_index = tracker.get_slot("schedule_interview_job_index")
        if schedule_interview_job_index is None:
            logger.warning("Slot schedule_interview_job_index is None")
            return RESET_SELECTED_JOB_EVENTS

        try:
            job_idx = int(schedule_interview_job_index)
        except ValueError:
            logger.warning("Slot schedule_interview_job_index cannot be converted to int")
            return RESET_SELECTED_JOB_EVENTS

        if 0 <= job_idx < len(jobs):
            logger.debug("schedule_interview_job_index is valid")
            chosen_job = jobs[job_idx]
            return [
                SlotSet("schedule_interview_job", chosen_job.model_dump(by_alias=True)),
                SlotSet("job_title", chosen_job.name),
            ]

        logger.warning("schedule_interview_job_index is out of range")
        return RESET_SELECTED_JOB_EVENTS
