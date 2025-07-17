from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_contacts, add_contact, Contact

class ScheduleDoctorAppointment(Action):

    def name(self) -> str:
        return "schedule_doctor_appointment"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        # Placeholder for scheduling logic
        return [SlotSet("return_value", "success")]
