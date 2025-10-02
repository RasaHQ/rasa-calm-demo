from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.shared_context import SharedContext
from actions.shared_context_events import (
    CreditCard,
    DigitalWalletActivationStarted,
    common_event_field_values,
)


class StartDigitalWalletActivation(Action):
    def name(self) -> str:
        return "start_digital_wallet_activation"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> list:
        SharedContext.store(
            DigitalWalletActivationStarted(
                card=CreditCard(
                    card_number="1234-5678-9012-3456",
                    cardholder_name="John Doe",
                    expiration_date="12/26",
                    cvv="123",
                    billing_address="123 Main St, Anytown, USA",
                ),
                **common_event_field_values(),
                tags=["rasa", "flow_started", "activate_digital_wallet"],
            )
        )
        return []
