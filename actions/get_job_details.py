import logging
from typing import Any

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.services import get_job_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionGetJobDetails(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_get_job_details"

    @module_monitor("schedule_interview", "action_get_job_details")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metadata = get_user_metadata(tracker)
        logger.debug(f"action get job details: metadata {metadata}")
        context = get_context(metadata)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []

        # TODO: use new slots from `action_ask_schedule_interview_job_index`
        # 1. Switch to using job ID to find related job ads
        # 2. Update the service and API client to use job ID
        job_title = tracker.get_slot("job_title")
        job_service = get_job_service()
        company_id = context.x_caller_identity.company_id
        jobads = await job_service.search_job_ads(company_id, job_title, context, 1)
        logger.info(f"number of found job ads: {len(jobads)}")

        # to introduce logic in fetching the most similar job
        if not jobads:
            return []

        jobad = jobads[0]
        if jobad.job_id is None:
            logger.warning("No job_id in jobad")
            return []

        job_geo_coordinates = await job_service.extract_job_geocoords(jobad, context)

        actions = [
            SlotSet("job_id", jobad.job_id),
            SlotSet("job_title", jobad.job_title),
        ]
        if jobad.location and jobad.location.city:
            actions.append(SlotSet("location", jobad.location.city))
        if jobad.create_date:
            actions.append(
                SlotSet("job_creation_date", jobad.create_date.isoformat()),
            )
        actions.extend(
            [
                SlotSet("job_state", jobad.job_ad_state),
                SlotSet("job_geo_coordinates", job_geo_coordinates),
            ]
        )
        return actions
