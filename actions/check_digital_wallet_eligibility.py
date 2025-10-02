from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher


class CheckDigitalWalletEligibility(Action):
    def name(self) -> str:
        return "check_digital_wallet_eligibility"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        return [SlotSet("digital_wallet_eligibility", "eligible")]
