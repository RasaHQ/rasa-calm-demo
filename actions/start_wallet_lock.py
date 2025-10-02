from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import SharedContext
from actions.shared_context_events import (
    CreditCard,
    WalletLockStarted,
    common_event_field_values,
)


## NOTE: This is a stub implementation.
## This event should be created by a backend service
class ActionStartWalletLock(Action):
    def name(self) -> str:
        return "start_wallet_lock"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        SharedContext.store(
            WalletLockStarted(
                **common_event_field_values(),
                tags=["rasa", "flow_started", "wallet_lock"],
                card=CreditCard(
                    card_number="4111 1111 1111 1111",
                    cardholder_name="John Doe",
                    expiration_date="12/25",
                    cvv="123",
                    billing_address="123 Main St, Anytown, USA",
                ),
            )
        )

        return []
