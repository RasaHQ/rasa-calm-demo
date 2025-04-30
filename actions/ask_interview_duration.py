import logging
from typing import Any

from rasa_sdk import Tracker
from sa_commons_monitoring import module_monitor

from app.constants import OTHER

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import Button, SingleChoicePayload

logger = logging.getLogger(__name__)


class ActionAskInterviewDuration(BaseAction[SingleChoicePayload]):
    def name(self) -> str:
        return "action_ask_interview_duration"

    @module_monitor("schedule_interview", "action_ask_interview_duration")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[SingleChoicePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        dispatcher.send_template_message(
            template="utter_ask_interview_duration_message",
            payload=SingleChoicePayload(
                options=[
                    Button(
                        title="30 minutes",
                        payload="/SetSlots(interview_duration=30)",
                    ),
                    Button(
                        title="45 minutes",
                        payload="/SetSlots(interview_duration=45)",
                    ),
                    Button(
                        title="60 minutes",
                        payload="/SetSlots(interview_duration=60)",
                    ),
                    Button(
                        title=OTHER,
                        payload=f"/SetSlots(interview_duration={OTHER})",
                    ),
                ],
            ),
        )
        return events
