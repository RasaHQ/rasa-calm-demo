import logging
import random
from typing import Any

from rasa_sdk import Tracker
from sa_commons_monitoring import module_monitor

from app.sr_core.converters.availability_calculator import get_current_time

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import Button, SingleChoicePayload

logger = logging.getLogger(__name__)

FRIDAY_WEEKDAY_NUMBER = 4


class ActionAskWeeksUntilInterview(BaseAction[SingleChoicePayload]):
    def name(self) -> str:
        return "action_ask_weeks_until_interview"

    @module_monitor("schedule_interview", "action_ask_weeks_until_interview")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[SingleChoicePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        date_now = get_current_time(tracker.get_slot("interviewer_timezone"))
        current_weekday_number = date_now.weekday()
        dispatcher.send_template_message(
            template="utter_display_weeks_until_interview_message",
            payload=SingleChoicePayload(
                options=ActionAskWeeksUntilInterview._scheduling_time_slot_buttons(current_weekday_number)
            ),
        )
        return events

    @staticmethod
    def _scheduling_time_slot_buttons(current_weekday_number: int) -> list[Button]:
        if current_weekday_number > FRIDAY_WEEKDAY_NUMBER:
            return ActionAskWeeksUntilInterview._scheduling_time_slot_next_week()
        elif current_weekday_number == FRIDAY_WEEKDAY_NUMBER:
            time_slots = ActionAskWeeksUntilInterview._scheduling_time_slot_this_week_friday()
        else:
            time_slots = ActionAskWeeksUntilInterview._scheduling_time_slot_this_week_before_friday(
                current_weekday_number
            )
        time_slots.extend(ActionAskWeeksUntilInterview._scheduling_time_slot_next_week())
        return random.sample(time_slots, 3)

    @staticmethod
    def _scheduling_time_slot_this_week_before_friday(current_weekday_number: int) -> list[Button]:
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        all_day_payload = ActionAskWeeksUntilInterview._join_weekday_payload(
            weekday_names, current_weekday_number, "09:00", "17:00"
        )
        every_afternoon_payload = ActionAskWeeksUntilInterview._join_weekday_payload(
            weekday_names, current_weekday_number, "12:00", "17:00"
        )
        every_morning_payload = ActionAskWeeksUntilInterview._join_weekday_payload(
            weekday_names, current_weekday_number, "09:00", "12:00"
        )

        return [
            Button(
                title="All day long this week",
                payload=f"/SetSlots(weeks_until_interview=0,interview_weekday_time=[{all_day_payload}])",
            ),
            Button(
                title="Every afternoon this week",
                payload=f"/SetSlots(weeks_until_interview=0,interview_weekday_time=[{every_afternoon_payload}])",
            ),
            Button(
                title="Every morning this week",
                payload=f"/SetSlots(weeks_until_interview=0,interview_weekday_time=[{every_morning_payload}])",
            ),
        ]

    @staticmethod
    def _join_weekday_payload(
        weekday_names: list[str], current_weekday_number: int, start_time: str, end_time: str
    ) -> str:
        return ";".join(
            [
                "{" + f"'{weekday_names[i]}'; '{start_time}'; '{end_time}' " + "}"
                for i in range(current_weekday_number, len(weekday_names))
            ]
        )

    @staticmethod
    def _scheduling_time_slot_this_week_friday() -> list[Button]:
        return [
            Button(
                title="Today all day long",
                payload="/SetSlots(weeks_until_interview=1,interview_weekday_time=[{'Friday'; '09:00'; '17:00'}])",
            ),
            Button(
                title="Today afternoon",
                payload="/SetSlots(weeks_until_interview=1,interview_weekday_time=[{'Friday'; '12:00'; '17:00'}])",
            ),
        ]

    @staticmethod
    def _scheduling_time_slot_next_week() -> list[Button]:
        return [
            Button(
                title="All day long next week",
                payload="/SetSlots(weeks_until_interview=1,interview_weekday_time="
                "[{'Monday'; '09:00'; '17:00'}; {'Tuesday'; '09:00'; '17:00'};"
                " {'Wednesday'; '09:00'; '17:00'}; {'Thursday'; '09:00'; '17:00'};"
                " {'Friday'; '09:00'; '17:00'}])",
            ),
            Button(
                title="Every morning next week",
                payload="/SetSlots(weeks_until_interview=1,interview_weekday_time="
                "[{'Monday'; '09:00'; '12:00'}; {'Tuesday'; '09:00'; '12:00'};"
                " {'Wednesday'; '09:00'; '12:00'}; {'Thursday'; '09:00'; '12:00'};"
                " {'Friday'; '09:00'; '12:00'}])",
            ),
            Button(
                title="Every afternoon next week",
                payload="/SetSlots(weeks_until_interview=1,interview_weekday_time="
                "[{'Monday'; '12:00'; '17:00'}; {'Tuesday'; '12:00'; '17:00'};"
                " {'Wednesday'; '12:00'; '17:00'}; {'Thursday'; '12:00'; '17:00'};"
                " {'Friday'; '12:00'; '17:00'}])",
            ),
        ]
