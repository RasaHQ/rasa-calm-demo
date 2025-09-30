from typing import Any, Dict, List, Optional, cast

import requests
import structlog
from pydantic import AwareDatetime, BaseModel, Field

from actions.shared_context_events import (
    CreditCardBlocked,
    Event,
    EventsList,
    TravelBookingStarted,
    deserialise_events,
)

logger = structlog.get_logger(__name__)


class TimeRange(BaseModel):
    start: AwareDatetime
    end: AwareDatetime


class SingleQueryInput(BaseModel):
    time_range: Optional[TimeRange] = Field(
        default=None, description="Time range for the query"
    )
    additional_filters: Dict[str, Any] = Field(
        default_factory=dict, description="Additional filters for the query"
    )


class QueryInput(BaseModel):
    queries: list[SingleQueryInput] = Field(
        default_factory=list,
        description="List of query inputs. If multiple are provided, each query "
        "is processed separately and results are merged",
    )
    count: int = Field(default=3, description="Maximum number of results to return")


class RecentEventsInput(BaseModel):
    count: int = Field(
        default=3, description="Maximum number of recent events to return"
    )
    types: Optional[list[str]] = Field(
        default=None, description="If provided, only events of these types are returned"
    )
    user_id: Optional[str] = Field(
        default=None, description="If provided, only events for this user are returned"
    )


class SharedContext:
    @staticmethod
    def get(query_input: QueryInput) -> EventsList:
        """Retrieve shared context based on the provided query input.

        Args:
            query_input (QueryInput): The input query parameters.

        Returns:
            Optional[Dict[str, Any]]: The retrieved context or None if not found.
        """
        # Placeholder implementation

        response = requests.post(
            "http://localhost:9080/query/",
            json=query_input.model_dump(mode="json"),
        )

        if response.status_code == 200:
            data: List[Any] = response.json()
            return deserialise_events(data)

        if response.status_code == 422:
            logger.info(
                "shred_context.unprocessable_query_submitted",
                message="Unprocessable query submitted to shared context service",
                query=query_input.model_dump_json(),
            )  # type: ignore
            return []

        raise Exception("Failed to retrieve context")

    @staticmethod
    def get_recent_events(recent_events_input: RecentEventsInput) -> EventsList:
        """Retrieve recent events based on the provided input.

        Args:
            recent_events_input (RecentEventsInput): The input parameters for recent events.

        Returns:
            EventsList: The list of recent events.
        """
        response = requests.get(
            "http://localhost:9080/events/recent",
            params=recent_events_input.model_dump(),
        )

        if response.status_code == 200:
            data: List[Any] = response.json()
            return deserialise_events(data)

        if response.status_code == 422:
            logger.info(
                "shred_context.unprocessable_recent_events_query_submitted",
                message="Unprocessable recent events query submitted to shared context service",
                query=recent_events_input.model_dump_json(),
            )  # type: ignore
            return []

        raise Exception("Failed to retrieve recent events")

    @staticmethod
    def store(event: Event) -> None:
        """Store an event in the shared context.

        Args:
            event (Dict[str, Any]): The event to store.
        """
        response = requests.post(
            "http://localhost:9080/events/",
            json=event.model_dump(mode="json"),
        )

        if response.status_code == 422:
            logger.info(
                "shared_context.invalid_event_submitted",
                message="Invalid event submitted to shared context service",
                event_data=event.model_dump_json(),
            )  # type: ignore
            raise ValueError("Invalid event data provided.")

        if response.status_code == 500:
            logger.error(
                "shared_context.server_error",
                message="Server error occurred in shared context service",
                event_data=event.model_dump_json(),
            )  # type: ignore
            raise Exception("Server error occurred in shared context service")

        if response.status_code != 200:
            logger.error(
                "shared_context.unknown_error",
                message="Unknown error occurred in shared context service",
                status_code=response.status_code,
                event_data=event.model_dump_json(),
            )  # type: ignore
            raise Exception("Unknown error occurred in shared context service")

        logger.info(
            "shared_context.event_stored",
            message="Event successfully stored in shared context service",
            event_data=event.model_dump_json(),
        )  # type: ignore


def find_blocked_card(events: EventsList) -> Optional[CreditCardBlocked]:
    # Start from the end of the list and look for the first TravelBookingStarted event
    # Events are assumed to be in descending order by timestamp
    for event in events:
        if event.type == "credit_card_blocked":
            # Check if there's a corresponding TravelBooked event after this
            started_event = event
            for subsequent_event in events[events.index(started_event) :]:
                if subsequent_event.type == "credit_card_unblocked":
                    return None  # Found a matching TravelBooked event, so no unfinished flow
            # If we reach here, it means there's no matching TravelBooked event
            return cast(CreditCardBlocked, started_event)
    return None  # No TravelBookingStarted event found


def find_unfinished_travel_booking(
    events: EventsList,
) -> Optional[TravelBookingStarted]:
    # Start from the end of the list and look for the first TravelBookingStarted event
    # Events are assumed to be in descending order by timestamp
    for event in events:
        if event.type == "travel_booking_started":
            # Check if there's a corresponding TravelBooked event after this
            started_event = event
            for subsequent_event in events[: events.index(started_event)]:
                if subsequent_event.type == "travel_booked":
                    return None  # Found a matching TravelBooked event, so no unfinished flow
            # If we reach here, it means there's no matching TravelBooked event
            return cast(TravelBookingStarted, started_event)
    return None  # No TravelBookingStarted event found
