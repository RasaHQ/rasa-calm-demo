import ast
import calendar
import logging
from datetime import datetime
from typing import Any

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from sa_commons_monitoring import module_monitor

from app.sr_core import converters
from app.sr_core.utils import correct_past_time_slots, parse_nontrivial_weekdays

from ...shared.base_action import BaseAction, CollectingDispatcherWrapper
from ...shared.domain_payload import NonePayload

logger = logging.getLogger(__name__)


class ActionCalculateInterviewAvailability(BaseAction[NonePayload]):
    def name(self) -> str:
        return "action_calculate_interviewer_availability"

    @module_monitor("schedule_interview", "action_calculate_interviewer_availability")
    async def _run_action(
        self,
        dispatcher: CollectingDispatcherWrapper[NonePayload],
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        interviewer_timezone = tracker.get_slot("interviewer_timezone")
        interview_weekday_time = tracker.get_slot("interview_weekday_time")
        interview_weekday_time = interview_weekday_time.replace("{", "(").replace("}", ")").replace(";", ",")
        interview_weekday_times = ast.literal_eval(interview_weekday_time)
        weeks_until_interview = tracker.get_slot("weeks_until_interview")
        current_time = converters.get_current_time(interviewer_timezone)
        weekdays = set(calendar.day_name)
        for i, (weekday, start_time, end_time) in enumerate(interview_weekday_times):
            if weekday not in weekdays:
                correct_weekday = parse_nontrivial_weekdays(weekday, current_time)
                interview_weekday_times[i] = (
                    correct_weekday,
                    start_time,
                    end_time,
                )

        available_times_converted_to_datetime_in_interviewer_timezone = converters.calculate_availabilities(
            current_time=current_time,
            weeks_to_interview=weeks_until_interview,
            weekdays_time=interview_weekday_times,
        )

        available_times_converted_datetime_in_utc = []
        for available_start_time, available_end_time in available_times_converted_to_datetime_in_interviewer_timezone:
            converted_start_time_in_utc = converters.convert_time(
                original_time=available_start_time,
                original_timezone=interviewer_timezone,
                destination_timezone="UTC",
            )
            converted_end_time_in_utc = converters.convert_time(
                original_time=available_end_time,
                original_timezone=interviewer_timezone,
                destination_timezone="UTC",
            )

            available_times_converted_datetime_in_utc.append(
                (
                    converted_start_time_in_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    converted_end_time_in_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                )
            )
        interviewer_availability = "\n".join(
            [
                f"{item0[0]}, {datetime.strptime(item1[0], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d-%m-%Y')}"
                f" {item0[1]}-{item0[2]}"
                for item0, item1 in zip(
                    interview_weekday_times,
                    available_times_converted_datetime_in_utc,
                    strict=False,
                )
            ]
        )

        validated_availability_times = correct_past_time_slots(
            interviewer_availability, current_time, interviewer_timezone
        )

        return [
            SlotSet("interviewer_availability_within_timezone", interviewer_availability),
            SlotSet("interviewer_availability_utc", str(available_times_converted_datetime_in_utc)),
            SlotSet(
                "corrected_interviewer_availability_within_timezone",
                validated_availability_times["interviewer_availability_within_timezone"],
            ),
            SlotSet(
                "corrected_interviewer_availability_utc",
                str(validated_availability_times["interviewer_availability_utc"]),
            ),
        ]
