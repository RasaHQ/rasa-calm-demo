import logging
from typing import Any, Literal

from pydantic import Field
from rasa_sdk import Tracker
from sa_commons_monitoring import module_monitor

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import BasePayload

logger = logging.getLogger(__name__)


class SearchCriterion(BasePayload):
    title: str = ""
    payload: str = ""


class ActionAskSearchFilterCriteriaPayload(BasePayload):
    type: Literal["action_ask_search_filter_criteria"] = "action_ask_search_filter_criteria"
    search_criteria: list[SearchCriterion] = Field(default_factory=list)


class ActionAskSearchFilterCriteria(BaseAction[ActionAskSearchFilterCriteriaPayload]):
    def name(self) -> str:
        return "action_ask_search_filter_criteria"

    @module_monitor("schedule_interview", "action_ask_search_filter_criteria")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[ActionAskSearchFilterCriteriaPayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if (
            tracker.get_slot("number_of_candidates_to_interview_with") is None
            or tracker.get_slot("search_filter_criteria") is None
        ):
            location = tracker.get_slot("location")
            dispatcher.send_template_message(
                template="utter_ask_candidate_search_filter_criteria",
                payload=ActionAskSearchFilterCriteriaPayload(
                    search_criteria=[
                        SearchCriterion(
                            title="5 star candidates",
                            payload="/SetSlots(search_filter_criteria={'min_star': 5})",
                        ),
                        SearchCriterion(
                            title="within 10 km",
                            payload="/SetSlots(search_filter_criteria={'radius_in_km': '10'})",
                        ),
                        SearchCriterion(
                            title=f"within city {location}",
                            payload=f"/SetSlots(search_filter_criteria={{'city': '{location}'}})",
                        ),
                    ]
                ),
            )
        return events
