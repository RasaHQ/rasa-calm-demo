import ast
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field
from rasa_sdk import Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.api_clients.search import SearchFilters
from app.sr_core.models.location import GeoLocation
from app.sr_core.services import get_candidate_service

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import BasePayload

logger = logging.getLogger(__name__)


class Candidate(BaseModel):
    first_name: str = Field(...)
    last_name: str = Field(...)


class CandidatesListPayload(BasePayload):
    type: Literal["candidates_list"] = "candidates_list"
    candidates: list[Candidate] = Field(default_factory=list)


class ActionGetCandidateIds(BaseAction[CandidatesListPayload]):
    def name(self) -> str:
        return "action_get_candidate_ids"

    @module_monitor("schedule_interview", "action_get_candidate_ids")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[CandidatesListPayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        # call search-api
        metadata = get_user_metadata(tracker)
        logger.debug(f"action get candidates: metadata {metadata}")
        context = get_context(metadata)
        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []

        candidate_service = get_candidate_service()
        criteria = ast.literal_eval(tracker.get_slot("search_filter_criteria"))
        if criteria.get("min_star", None):
            criteria["min_star"] = int(criteria["min_star"])

        search_filters = SearchFilters.model_validate(criteria)
        search_filters.job_legacy_id = tracker.get_slot("job_id")

        geocoords = tracker.get_slot("job_geo_coordinates")
        geocoords = await candidate_service.get_geocoords_for_candidate_criteria(
            GeoLocation.model_validate(geocoords), search_filters, context
        )

        # We intitalized this slot as GeoCoordinates object, but turns out that RASA internally
        # converts it to a dictionary
        search_filter_criteria_updated = search_filters.model_copy()
        if geocoords:
            search_filter_criteria_updated.latlng = f"{geocoords.lat},{geocoords.lon}"

        num_candidates_to_interview = min(int(tracker.get_slot("number_of_candidates_to_interview_with")), 10)
        all_candidates = await candidate_service.search_candidates(
            filters=search_filter_criteria_updated,
            limit=num_candidates_to_interview,
            context=context,
        )
        top_candidates = all_candidates[:num_candidates_to_interview]
        candidates_ids = [candidate.hash_code_uuid for candidate in top_candidates]
        candidates_names = [f"{candidate.first_name} {candidate.last_name}" for candidate in top_candidates]
        candidates_info = "\n".join(
            f"{candidate.first_name} {candidate.last_name}: {candidate.email_address}" for candidate in top_candidates
        )

        candidates_count = len(candidates_ids)

        if candidates_count == 0:
            dispatcher.send_template_message(template="utter_no_candidates_found")
            return [
                SlotSet("search_filter_criteria", None),
                FollowupAction("action_ask_search_filter_criteria"),
            ]

        candidates = [
            Candidate(first_name=candidate.first_name or "", last_name=candidate.last_name or "")
            for candidate in top_candidates
        ]

        dispatcher.send_template_message(
            template="utter_found_candidates",
            retrieved_candidates_count=candidates_count,
            retrieved_candidates_info=candidates_info,
            payload=CandidatesListPayload(candidates=candidates),
        )

        return [
            SlotSet("retrieved_candidates_names", candidates_names),
            SlotSet("retrieved_candidates_info", candidates_info),
            SlotSet("retrieved_candidates_ids", candidates_ids),
            SlotSet("retrieved_candidates_count", len(candidates_ids)),
        ]
