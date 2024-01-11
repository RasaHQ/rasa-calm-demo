from typing import Any, Dict
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from actions.db import get_transactions


class TransactionSearch(Action):

    def name(self) -> str:
        return "transaction_search"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[str, Any]):
        transactions = get_transactions(tracker.sender_id)
        transactions_list = "\n".join([t.stringify() for t in transactions])
        return [SlotSet("transactions_list", transactions_list)]
