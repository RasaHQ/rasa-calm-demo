from __future__ import annotations

import datetime
from typing import Annotated, Any, ClassVar, Dict, List, Literal, Optional, Type, Union

from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter, ValidationError

from actions.common import user_id

EventSource = Annotated[Literal["web", "mobile_app", "Rasa"], Field(default="web")]


class Event(BaseModel):
    # type: ClassVar[str] = Field(description="Type of the event")

    timestamp: AwareDatetime = Field(description="Timestamp of the event")
    schema_version: str = Field(
        default="1.0", description="Schema version of the event"
    )
    tags: List[str] = Field(default_factory=list, description="List of tags")
    user_id: Optional[str] = Field(default=None, description="User ID")
    source: EventSource

    def is_type(self, event_type: Type[Event]) -> bool:
        return isinstance(self, event_type)


class StarterEvent(Event):
    @staticmethod
    def flow_name() -> str:
        raise NotImplementedError("Subclasses should implement this method")

    def continuation_message(self) -> str:
        raise NotImplementedError("Subclasses should implement this method")


class CreditCard(BaseModel):
    card_number: str = Field(description="Credit card number")
    cardholder_name: str = Field(description="Name of the cardholder")
    expiration_date: str = Field(description="Expiration date of the card")
    cvv: str = Field(description="CVV code of the card")
    billing_address: str = Field(description="Billing address associated with the card")


class CreditCardBlocked(Event):
    type: Literal["credit_card_blocked"] = Field(
        default="credit_card_blocked", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card blocked")
    reason: Optional[str] = Field(
        default=None, description="Reason for blocking the card"
    )


class CreditCardUnblocked(Event):
    type: Literal["credit_card_unblocked"] = Field(
        default="credit_card_unblocked", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card unblocked")
    reason: Optional[str] = Field(
        default=None, description="Reason for unblocking the card"
    )


class CreditCardDelivered(Event):
    type: Literal["credit_card_delivered"] = Field(
        default="credit_card_delivered", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card delivered")


class Currency(BaseModel):
    code: Literal["USD", "EUR"] = Field(description="Currency code, e.g., USD, EUR")
    amount: float = Field(description="Amount in the specified currency")


class BankAccountPayment(BaseModel):
    type: Literal["bank_account_transfer"] = Field(
        default="bank_account_transfer", description="Type of the payment"
    )
    amount: Currency = Field(description="Amount of the payment")
    from_account: str = Field(
        description="Bank account number from which the payment is made"
    )
    to_account: str = Field(
        description="Bank account number to which the payment is made"
    )


class CreditCardPayment(BaseModel):
    type: Literal["credit_card"] = Field(
        default="credit_card", description="Type of the payment"
    )
    card_number: str = Field(description="Credit card number")
    amount: Currency = Field(description="Amount of the payment")


Payment = Annotated[
    Union["BankAccountPayment", "CreditCardPayment"],
    Field(discriminator="type"),
]


class TravelBooked(Event):
    type: Literal["travel_booked"] = Field(
        default="travel_booked", description="Type of the event"
    )

    destination: str = Field(description="Travel destination")
    start_date: AwareDatetime = Field(description="Start date of the travel")
    end_date: AwareDatetime = Field(description="End date of the travel")
    payment: Payment = Field(description="Payment details for the travel booking")


class TravelBookingStarted(StarterEvent):
    type: Literal["travel_booking_started"] = Field(
        default="travel_booking_started", description="Type of the event"
    )

    destination: str = Field(description="Travel destination")
    start_date: AwareDatetime = Field(description="Start date of the travel")
    end_date: AwareDatetime = Field(description="End date of the travel")

    @staticmethod
    def flow_name() -> str:
        return f"flow_book_a_flight"

    def continuation_message(self) -> str:
        return (
            f"Heya, we noticed you started booking a flight "
            f"earlier to {self.destination}. "
            "Let's continue where we left off!"
        )


class WalletLockStarted(StarterEvent):
    type: Literal["wallet_lock_started"] = Field(
        default="wallet_lock_started", description="Type of the event"
    )

    card: Optional[CreditCard] = Field(
        default=None, description="Credit card of the wallet lock"
    )

    @staticmethod
    def flow_name() -> str:
        return f"flow_lock_wallet"

    def continuation_message(self) -> str:
        if not self.card:
            return (
                f"Hi, I see you started the process to lock your wallet. "
                "Would you like to continue?"
            )

        return (
            f"Hi, I see you started the process to lock your wallet containing "
            f"the card ending in {self.card.card_number[-4:]}. "
            f"Would you to continue?"
        )


class WalletLockingUpdated(Event):
    type: Literal["wallet_locking_updated"] = Field(
        default="wallet_locking_updated", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card of the wallet lock")


class WalletLockCompleted(Event):
    type: Literal["wallet_lock_completed"] = Field(
        default="wallet_lock_completed", description="Type of the event"
    )


class DigitalWalletActivationStarted(StarterEvent):
    type: Literal["digital_wallet_activation_started"] = Field(
        default="digital_wallet_activation_started", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card for digital wallet")

    @staticmethod
    def flow_name() -> str:
        return f"flow_activate_digital_wallet"

    def continuation_message(self) -> str:
        if not self.card:
            return (
                f"Hi, I see you started the process to activate your digital wallet. "
                "Do you need any help?"
            )

        return (
            f"Hi, I see you started the process to activate your digital wallet "
            f"with the card ending in {self.card.card_number[-4:]}. Do you need any help?"
        )


class DigitalWalletActivated(Event):
    type: Literal["digital_wallet_activated"] = Field(
        default="digital_wallet_activated", description="Type of the event"
    )

    card: CreditCard = Field(description="Credit card for digital wallet")


class HumanHandoffRequested(Event):
    type: Literal["human_handoff_requested"] = Field(
        default="human_handoff_requested", description="Type of the event"
    )

    reason: Optional[str] = Field(
        default=None, description="Reason for requesting human handoff"
    )

    current_state: Dict[str, Any] = Field(
        default_factory=dict, description="Current state of the conversation"
    )


Events = Annotated[
    Union[
        TravelBookingStarted,
        TravelBooked,
        CreditCardUnblocked,
        CreditCardBlocked,
        CreditCardDelivered,
        WalletLockStarted,
        WalletLockingUpdated,
        WalletLockCompleted,
        DigitalWalletActivationStarted,
        DigitalWalletActivated,
    ],
    Field(discriminator="type"),
]


EventsList = List[Events]
AllEventsListAdapter = TypeAdapter(EventsList)


def deserialise_events(serialized_events: List[Dict[str, Any]]) -> EventsList:
    """Convert a list of dictionaries to a list of corresponding events.

    Example format:
        [{"event": "slot", "value": 5, "name": "my_slot"}]
    """
    try:
        return AllEventsListAdapter.validate_python(serialized_events)  # type: ignore[return-value]
    except ValidationError as e:
        raise ValueError(f"Failed to deserialize events. {e}") from e


def common_event_field_values() -> Dict:
    return {
        "schema_version": "1.0.0",
        "user_id": user_id,
        "source": "Rasa",
        "timestamp": str(datetime.datetime.now(datetime.UTC).isoformat()),
    }
