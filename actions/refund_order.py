from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_account


class ProcessRefundRequest(Action):

    def name(self) -> str:
        return "action_process_refund_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        pass
