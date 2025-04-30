from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import Field, TypeAdapter
from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from app.context import ContextLoaderFn, context_loader
from app.sr_core.models.job import JobSearchDocument
from app.sr_core.services import JobService, get_job_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import BasePayload

logger = logging.getLogger(__name__)


class ScheduleInterviewJob(BasePayload):
    # TODO double check which ID do we need here.
    # We should have right identifier for JobAds fetching API call
    external_id: str
    name: str
    location: str | None = None
    # TODO check what do we need to WEB and WhatApp renders

    @staticmethod
    def parse_interviewer_jobs(interviewer_jobs: list[JobSearchDocument]) -> list[ScheduleInterviewJob]:
        # TODO think about saving whole response here to use other fields when we would need them
        return [
            ScheduleInterviewJob(
                # TODO we assume that external_id always here. Why?
                external_id=str(job.external_id),
                name=job.name,
                location=job.location_string,
            )
            for job in interviewer_jobs
            if job.name
        ]


ScheduleInterviewJobsTypeAdapter = TypeAdapter(list[ScheduleInterviewJob])


class ScheduleInterviewJobsPayload(BasePayload):
    type: Literal["schedule_interview_jobs"] = "schedule_interview_jobs"
    jobs: list[ScheduleInterviewJob] = Field(default_factory=list)


class ActionAskScheduleInterviewJobIndex(BaseAction[ScheduleInterviewJobsPayload]):
    def __init__(
        self, job_service: JobService | None = None, context_loader_fn: ContextLoaderFn = context_loader
    ) -> None:
        super().__init__()
        self._job_service = job_service or get_job_service()
        self._context_loader_fn = context_loader_fn

    def name(self) -> str:
        return "action_ask_schedule_interview_job_index"

    @module_monitor("schedule_interview", "action_ask_schedule_interview_job_index")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[ScheduleInterviewJobsPayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        interviewer_jobs = await self._retrieve_all_jobs_for_interviewer(tracker)
        jobs = ScheduleInterviewJob.parse_interviewer_jobs(interviewer_jobs)

        events.extend(
            (
                SlotSet(
                    "schedule_interview_found_jobs",
                    ScheduleInterviewJobsTypeAdapter.dump_python(jobs, by_alias=True),
                ),
                SlotSet("schedule_interview_found_job_count", str(len(jobs))),
            )
        )

        dispatcher.send_template_message(
            "utter_ask_schedule_interview_jobs_found",
            job_count=len(jobs),
            payload=ScheduleInterviewJobsPayload(jobs=jobs),
        )

        return events

    async def _retrieve_all_jobs_for_interviewer(self, tracker: Tracker) -> list[JobSearchDocument]:
        context = self._context_loader_fn(tracker)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []

        return await self._job_service.retrieve_all_jobs_for_interviewer(
            interviewer_ids=[context.x_caller_identity.external_id],
            context=context,
        )
