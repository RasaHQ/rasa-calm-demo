import ast
import logging
from typing import Any

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from sa_commons_monitoring import module_monitor

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionBuildSelfScheduleConfirmationMessage(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_build_self_schedule_confirmation_message"

    @module_monitor("schedule_interview", "action_build_confirmation_message")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        weeks_to_interview = int(tracker.get_slot("weeks_until_interview"))

        interviewer_availability_within_timezone = tracker.get_slot(
            "corrected_interviewer_availability_within_timezone"
        )

        selected_candidates = ast.literal_eval(
            tracker.get_slot("selected_candidates_positions").replace(";", ",")
        )
        candidate_names = tracker.get_slot("retrieved_candidates_names")

        selected_candidate_names_text = self._get_selected_candidate_names_text(
            candidate_names,
            selected_candidates
        )

        weeks_until_interview_text = self._get_weeks_until_interview_text(
            weeks_to_interview
        )
        interview_type = tracker.get_slot("interview_type")
        dispatcher.send_text_message(
            text=(
                f"Got it, I'll send out the self-scheduling link for {interview_type} to these candidates: \n"
                f"{selected_candidate_names_text}\n"
                f"for {weeks_until_interview_text}. They will select time slots in the interval: \n"
                f"{interviewer_availability_within_timezone}\n"
            )
        )
        return []

    def _get_weeks_until_interview_text(self, weeks_to_interview: int) -> str:
        if weeks_to_interview > 1:
            return f"the next {weeks_to_interview} weeks"

        return "the next week" if weeks_to_interview == 1 else "this week"

    def _get_selected_candidate_names_text(self, candidate_names: list[str], selected_candidates: list[int]) -> str:
        selected_candidate_names_text = "\n".join(
            [candidate_names[i - 1] for i in selected_candidates]
        )
        return selected_candidate_names_text
