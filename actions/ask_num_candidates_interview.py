import ast
import logging
from typing import Any

from rasa_sdk import Action, Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from sa_commons_monitoring import module_monitor

from app.context import get_context, get_user_metadata
from app.sr_core.api_clients.search import SearchFilters
from app.sr_core.models.location import GeoLocation
from app.sr_core.services import get_candidate_service

logger = logging.getLogger(__name__)

CANDIDATES_NUM_LIMIT = 10


class ActionAskNumOfCandidatesToInterviewWith(Action):
    def name(self) -> str:
        return "action_ask_number_of_candidates_to_interview_with"

    @module_monitor("schedule_interview", "action_ask_number_of_candidates_to_interview_with")
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metadata = get_user_metadata(tracker)
        logger.debug(f"action ask number of candidates to interview with: metadata {metadata}")
        context = get_context(metadata)

        if context.x_caller_identity is None:
            logger.warning("No x_caller_identity in context")
            return []
        events: list[dict[str, Any]] = []
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

        total_num_candidates = await candidate_service.get_num_candidates(
            filters=search_filter_criteria_updated, context=context
        )
        criteria_message = ", ".join([f"{key.replace('_', ' ')}: {value}" for key, value in criteria.items()])
        if total_num_candidates == 0:
            dispatcher.utter_message(
                text=f"there is no candidate to interview with the given criteria: {criteria_message}"
            )
            return [
                SlotSet("search_filter_criteria", None),
                FollowupAction("action_ask_search_filter_criteria"),
            ]

        if total_num_candidates > CANDIDATES_NUM_LIMIT:
            max_num_candidates = CANDIDATES_NUM_LIMIT
        else:
            max_num_candidates = total_num_candidates

        if max_num_candidates == total_num_candidates:
            if max_num_candidates == 1:
                buttons_values = ["1"]
            else:
                buttons_values = [str(int(max_num_candidates / 2)), "everyone"]
        else:
            buttons_values = [
                str(int(max_num_candidates / 2)),
                str(max_num_candidates),
                "everyone",
            ]

        dispatcher.utter_message(
            text=f"Your selected criteria was {criteria_message}.\n "
            f"Based on it I found a total of {total_num_candidates} candidates available for interviews."
            " How many candidates would you like to shortlist for an"
            f" interview for the {tracker.get_slot('job_title')} role?",
            buttons=[
                {
                    "title": (
                        f"{value!s} candidate"
                        if value == "1"
                        else (f"{value!s} candidates" if value != "everyone" else value)
                    ),
                    "payload": "/SetSlots(number_of_candidates_to_interview_with="
                    f"{value if value != 'everyone' else str(total_num_candidates)})",
                }
                for value in buttons_values
            ],
        )
        return events
