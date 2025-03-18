from datetime import datetime
from typing import Any, Dict, Optional

from rasa.shared.nlu.training_data.message import Message
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from actions.setup_recurrent_payment import parse_datetime


def is_appointment_available(appointment_time: datetime) -> bool:
    weekday = appointment_time.weekday()
    # doctor has clinics only on Monday to Friday (0 to 4)
    if weekday in [5, 6]:
        return False

    hour = appointment_time.hour

    # doctor is available only between 9am to 5pm, excluding noon in-patient checks
    if hour < 9 or hour > 17 or 12 <= hour < 14:
        return False

    return True


class AppointmentSearch(Action):

    def name(self) -> str:
        return "action_check_appointment_availability"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        current_value = tracker.get_slot("appointment_time")
        if current_value is None:
            return []

        appointment_time = parse_datetime(current_value)
        available_appointments = [
            "Monday 9:00", "Monday 10:00", "Monday 11:00", "Monday 14:00",
            "Monday 15:00", "Monday 16:00", "Tuesday 9:00", "Tuesday 10:00",
            "Tuesday 11:00", "Tuesday 14:00", "Tuesday 15:00", "Tuesday 16:00",
            "Wednesday 9:00", "Wednesday 10:00", "Wednesday 11:00", "Wednesday 14:00",
            "Wednesday 15:00", "Wednesday 16:00", "Thursday 9:00", "Thursday 10:00",
            "Thursday 11:00", "Thursday 14:00", "Thursday 15:00", "Thursday 16:00",
            "Friday 9:00", "Friday 10:00", "Friday 11:00", "Friday 14:00",
            "Friday 15:00", "Friday 16:00"
        ]
        return [
            SlotSet("available_appointments", available_appointments),
            SlotSet("appointment_available", is_appointment_available(appointment_time))
        ]
