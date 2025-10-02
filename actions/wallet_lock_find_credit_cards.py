from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher


class WalletLockFindCreditCards(Action):
    def name(self) -> str:
        return "wallet_lock_find_credit_cards"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        return [
            SlotSet(
                "found_credit_cards",
                "1111",
            )
        ]
