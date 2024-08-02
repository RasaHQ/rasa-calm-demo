import asyncio
import logging
from functools import partial
from typing import NoReturn, Text, Dict, Any, Optional, Callable, Awaitable, Union

from asyncio import Queue, CancelledError
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse, ResponseStream

import structlog
import rasa.utils.endpoints
from rasa.core.channels.channel import InputChannel, CollectingOutputChannel, UserMessage
from rasa.core.channels.rest import RestInput

logger = logging.getLogger(__name__)
structlogger = structlog.get_logger()

class DelayedRestInput(RestInput):
    """A custom HTTP input channel with delayed message aggregation."""

    @classmethod
    def name(cls) -> Text:
        """Defines the name of the input channel."""
        return "delayed_rest"

    def __init__(self, message_delay: float = 2, queue_limit: int = 10):
        """Initializes the input channel with a specified message delay and queue limit."""
        super().__init__()
        self.message_delay = message_delay  # Time to wait before processing messages
        self.queue_limit = queue_limit  # Maximum number of messages in the queue
        self.user_queues: Dict[Text, Queue] = {}  # Queues for each user to hold their messages
        self.user_tasks: Dict[Text, asyncio.Task] = {}  # Tasks for processing messages for each user

    async def aggregate_messages(self, sender_id: Text) -> str:
        """Aggregates messages from a user's queue."""
        user_queue = self.user_queues.get(sender_id)
        if not user_queue:
            return ""

        messages = []
        while not user_queue.empty():
            messages.append(await user_queue.get())  # Retrieve all messages from the queue

        return " ".join(messages)  # Concatenate messages into a single string

    async def handle_message(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[None]],
        sender_id: Text,
        text: Text,
        input_channel: Text,
        metadata: Optional[Dict[Text, Any]],
    ) -> Optional[Dict[Text, Any]]:
        """Handles incoming messages by adding them to the queue and processing them."""
        if sender_id not in self.user_queues:
            self.user_queues[sender_id] = Queue(self.queue_limit)  # Create a new queue for the user if it doesn't exist

        try:
            await self.user_queues[sender_id].put(text)  # Add the message to the user's queue
        except asyncio.QueueFull:
            structlogger.warning("User queue is full", sender_id=sender_id, text=text)
            return {"error": "Queue full"}

        if sender_id in self.user_tasks and not self.user_tasks[sender_id].done():
            return  # If there's already a task running for the user, do nothing

        async def process_queue():
            """Processes the user's message queue after a delay."""
            await asyncio.sleep(self.message_delay)  # Wait for the specified delay
            aggregated_text = await self.aggregate_messages(sender_id)
            if aggregated_text:
                collector = CollectingOutputChannel()
                try:
                    # Process the aggregated message
                    await on_new_message(
                        UserMessage(
                            aggregated_text,
                            collector,
                            sender_id,
                            input_channel=input_channel,
                            metadata=metadata,
                        )
                    )
                except CancelledError:
                    structlogger.error(
                        "rest.message.received.timeout", text=copy.deepcopy(aggregated_text)
                    )
                except Exception as e:
                    structlogger.exception(
                        "rest.message.received.failure", text=copy.deepcopy(aggregated_text)
                    )
                finally:
                    # Clean up user-specific data after processing
                    self.user_queues.pop(sender_id, None)
                    self.user_tasks.pop(sender_id, None)

                return collector.messages  # Return the collected messages

        # Create a new task to process the user's queue
        self.user_tasks[sender_id] = asyncio.create_task(process_queue())
        return await self.user_tasks[sender_id]  # Await the task's result

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        """Defines the Sanic blueprint for handling HTTP requests."""
        custom_webhook = Blueprint("custom_webhook", __name__)

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            """Health check endpoint."""
            return response.json({"status": "ok"})

        @custom_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> Union[ResponseStream, HTTPResponse]:
            """Endpoint to receive messages."""
            sender_id = await self._extract_sender(request)
            text = self._extract_message(request)
            should_use_stream = rasa.utils.endpoints.bool_arg(request, "stream", default=False)
            input_channel = self._extract_input_channel(request)
            metadata = self.get_metadata(request)

            if sender_id is not None and text is not None:
                if should_use_stream:
                    return ResponseStream(
                        partial(self.stream_response, on_new_message, text, sender_id, input_channel, metadata),
                        content_type="text/event-stream",
                    )
                else:
                    messages = await self.handle_message(on_new_message, sender_id, text, input_channel, metadata)
                    return response.json(messages)
            else:
                return response.json({"status": "error", "message": "Invalid input"})

        return custom_webhook


class QueueOutputChannel(CollectingOutputChannel):
    """Output channel that collects sent messages in a list."""

    messages: Queue  # type: ignore[assignment]

    @classmethod
    def name(cls) -> Text:
        """Defines the name of the output channel."""
        return "queue"

    def __init__(self, message_queue: Optional[Queue] = None) -> None:
        """Initializes the output channel with an optional message queue."""
        super().__init__()
        self.messages = Queue() if not message_queue else message_queue

    def latest_output(self) -> NoReturn:
        """Raises an error because a queue doesn't allow peeking at messages."""
        raise NotImplementedError("A queue doesn't allow to peek at messages.")

    async def _persist_message(self, message: Dict[Text, Any]) -> None:
        """Persists messages by adding them to the queue."""
        await self.messages.put(message)
