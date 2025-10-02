import structlog
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import SharedContext
from actions.shared_context_events import WalletLockCompleted, common_event_field_values


class BlockCardsAndLockWallet(Action):
    def name(self) -> str:
        return "block_cards_and_lock_wallet"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        SharedContext.store(
            WalletLockCompleted(
                **common_event_field_values(),
                tags=["rasa", "flow_completed", "lock_wallet"],
            ),
        )
        return [SlotSet("digital_wallet_eligibility", "eligible")]
