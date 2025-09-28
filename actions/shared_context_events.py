from typing import Annotated, Any, ClassVar, Dict, List, Literal, Optional, Union

from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter, ValidationError

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


class TravelBookingStarted(Event):
    type: Literal["travel_booking_started"] = Field(
        default="travel_booking_started", description="Type of the event"
    )

    destination: str = Field(description="Travel destination")
    start_date: AwareDatetime = Field(description="Start date of the travel")
    end_date: AwareDatetime = Field(description="End date of the travel")


Events = Annotated[
    Union[
        TravelBookingStarted,
        TravelBooked,
        CreditCardUnblocked,
        CreditCardBlocked,
        CreditCardDelivered,
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
