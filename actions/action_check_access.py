import logging
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.db import get_account

logger = logging.getLogger(__name__)

class ActionCheckAccess(Action):
    def name(self) -> Text:
        return "action_check_access"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        authorized_functions = get_account(tracker.sender_id).authorized_functions
        flow_id = tracker.stack[0]['flow_id']

        if flow_id in authorized_functions:
            logger.info(f"flow_id {flow_id} is in authorized_functions {authorized_functions}")
            return [SlotSet("user_has_access", True)]
        
        return [SlotSet("user_has_access", False)]