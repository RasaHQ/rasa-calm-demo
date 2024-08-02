from copy import copy
import inspect
import logging
import json
import uuid
from typing import List, Text, Dict, Any, Optional, Callable, Awaitable, Iterable

import rasa.core.channels.channel
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, response, Sanic
from sanic.request import Request
from sanic.response import HTTPResponse
from socketio import AsyncServer
from asyncio import CancelledError, QueueFull, Task, Queue, create_task, sleep

logger = logging.getLogger(__name__)


class DelayedSocketIOBlueprint(Blueprint):
    """Blueprint for delayed socketio connections."""

    def __init__(
        self, sio: AsyncServer, socketio_path: Text, *args: Any, **kwargs: Any
    ) -> None:
        """Creates a :class:`sanic.Blueprint` for routing socketio connections.

        :param sio: Instance of :class:`socketio.AsyncServer` class
        :param socketio_path: string indicating the route to accept requests on.
        """
        super().__init__(*args, **kwargs)
        self.ctx.sio = sio
        self.ctx.socketio_path = socketio_path

    def register(self, app: Sanic, options: Dict[Text, Any]) -> None:
        """Attach the Socket.IO webserver to the given Sanic instance.

        :param app: Instance of :class:`sanic.app.Sanic` class
        :param options: Options to be used while registering the
            blueprint into the app.
        """
        self.ctx.sio.attach(app, self.ctx.socketio_path)
        super().register(app, options)


class DelayedSocketIOOutput(OutputChannel):
    @classmethod
    def name(cls) -> Text:
        return "delayed_socketio"

    def __init__(self, sio: AsyncServer, bot_message_evt: Text) -> None:
        self.sio = sio
        self.bot_message_evt = bot_message_evt

    async def _send_message(self, socket_id: Text, response: Any) -> None:
        """Sends a message to the recipient using the bot event."""
        await self.sio.emit(self.bot_message_evt, response, room=socket_id)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""
        for message_part in text.strip().split("\n\n"):
            await self._send_message(recipient_id, {"text": message_part})

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        """Sends an image to the output."""
        message = {"attachment": {"type": "image", "payload": {"src": image}}}
        await self._send_message(recipient_id, message)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        """Sends buttons to the output."""
        message_parts = text.strip().split("\n\n") or [text]
        messages: List[Dict[Text, Any]] = [
            {"text": message, "quick_replies": []} for message in message_parts
        ]

        messages[-1]["quick_replies"] = [
            {
                "content_type": "text",
                "title": button["title"],
                "payload": button.get("payload", button["title"]),
            }
            for button in buttons
        ]

        for message in messages:
            await self._send_message(recipient_id, message)

    async def send_elements(
        self, recipient_id: Text, elements: Iterable[Dict[Text, Any]], **kwargs: Any
    ) -> None:
        """Sends elements to the output."""
        for element in elements:
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": element},
                }
            }
            await self._send_message(recipient_id, message)

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends custom json to the output."""
        if "data" in json_message:
            json_message.setdefault("room", recipient_id)
            await self.sio.emit(self.bot_message_evt, **json_message)
        else:
            await self.sio.emit(self.bot_message_evt, json_message, room=recipient_id)

    async def send_attachment(
        self, recipient_id: Text, attachment: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends an attachment to the user."""
        await self._send_message(recipient_id, {"attachment": attachment})


class DelayedSocketIOInput(InputChannel):
    """A socket.io input channel with delayed message aggregation."""

    @classmethod
    def name(cls) -> Text:
        return "delayed_socketio"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        credentials = credentials or {}
        return cls(
            credentials.get("user_message_evt", "user_uttered"),
            credentials.get("bot_message_evt", "bot_uttered"),
            credentials.get("namespace"),
            credentials.get("session_persistence", False),
            credentials.get("socketio_path", "/socket.io"),
            credentials.get("jwt_key"),
            credentials.get("jwt_method", "HS256"),
            credentials.get("metadata_key", "metadata"),
            credentials.get("message_delay", 1.5),
            credentials.get("queue_limit", 10),
            credentials.get("cleanup_delay", 10),
        )

    def __init__(
        self,
        user_message_evt: Text = "user_uttered",
        bot_message_evt: Text = "bot_uttered",
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Optional[Text] = "/socket.io",
        jwt_key: Optional[Text] = None,
        jwt_method: Optional[Text] = "HS256",
        metadata_key: Optional[Text] = "metadata",
        message_delay: float = 1.5,
        queue_limit: int = 10,
        cleanup_delay: float = 10.0,

    ):
        """Creates a ``DelayedSocketIOInput`` object."""
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.sio: Optional[AsyncServer] = None
        self.metadata_key = metadata_key
        self.message_delay = message_delay
        self.queue_limit = queue_limit
        self.cleanup_delay = cleanup_delay
        self.user_queues: Dict[Text, Queue] = {}
        self.user_tasks: Dict[Text, Task] = {}
        self.cleanup_tasks: Dict[Text, Task] = {}

        self.jwt_key = jwt_key
        self.jwt_algorithm = jwt_method

    def get_output_channel(self) -> Optional["OutputChannel"]:
        """Creates socket.io output channel object."""
        if self.sio is None:
            rasa.shared.utils.io.raise_warning(
                "SocketIO output channel cannot be recreated. "
                "This is expected behavior when using multiple Sanic "
                "workers or multiple Rasa Pro instances. "
                "Please use a different channel for external events in these "
                "scenarios."
            )
            return None
        return DelayedSocketIOOutput(self.sio, self.bot_message_evt)

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
        sid: Text,
        data: Dict[Text, Any]
    ) -> None:
        """Handles incoming messages by adding them to the queue and processing them."""
        sender_id = data.get("session_id") or sid
        text = data.get("message")
        input_channel = self.name()
        metadata = data.get(self.metadata_key, {})

        if sender_id not in self.user_queues:
            self.user_queues[sender_id] = Queue(self.queue_limit)  # Create a new queue for the user if it doesn't exist

        try:
            await self.user_queues[sender_id].put(text)  # Add the message to the user's queue
        except QueueFull:
            logger.warning("User queue is full", sender_id=sender_id, text=text)
            return

        if sender_id in self.user_tasks and not self.user_tasks[sender_id].done():
            return  # If there's already a task running for the user, do nothing

        
        async def process_queue():
            """Processes the user's message queue after a delay."""
            await sleep(self.message_delay)  # Wait for the specified delay
            aggregated_text = await self.aggregate_messages(sender_id)
            if aggregated_text:
                collector = DelayedSocketIOOutput(self.sio, self.bot_message_evt)
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
                    logger.error(
                        "socketio.message.received.timeout", text=copy.deepcopy(aggregated_text)
                    )
                except Exception as e:
                    logger.exception
                    logger.exception(
                        "socketio.message.received.failure", text=copy.deepcopy(aggregated_text)
                    )
                finally:
                    # Schedule cleanup after the additional delay
                    self.cleanup_tasks[sender_id] = create_task(self.cleanup_user(sender_id))

        # Create a new task to process the user's queue
        self.user_tasks[sender_id] = create_task(process_queue())
        await self.user_tasks[sender_id]  # Await the task's result
    
    async def cleanup_user(self, sender_id: Text) -> None:
        """Cleans up the user's data after a delay."""
        await sleep(self.cleanup_delay)  # Wait for the specified cleanup delay
        self.user_queues.pop(sender_id, None)
        self.user_tasks.pop(sender_id, None)
        self.cleanup_tasks.pop(sender_id, None)

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        """Defines a Sanic blueprint."""
        sio = AsyncServer(async_mode="sanic", cors_allowed_origins=[])
        socketio_webhook = DelayedSocketIOBlueprint(
            sio, self.socketio_path, "socketio_webhook", __name__
        )

        # make sio object static to use in get_output_channel
        self.sio = sio

        @socketio_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @sio.on("connect", namespace=self.namespace)
        async def connect(sid: Text, environ: Dict, auth: Optional[Dict]) -> bool:
            if self.jwt_key:
                jwt_payload = None
                if auth and auth.get("token"):
                    jwt_payload = rasa.core.channels.channel.decode_bearer_token(
                        auth.get("token"), self.jwt_key, self.jwt_algorithm
                    )

                if jwt_payload:
                    logger.debug(f"User {sid} connected to socketIO endpoint.")
                    return True
                else:
                    return False
            else:
                logger.debug(f"User {sid} connected to socketIO endpoint.")
                return True

        @sio.on("disconnect", namespace=self.namespace)
        async def disconnect(sid: Text) -> None:
            logger.debug(f"User {sid} disconnected from socketIO endpoint.")

        @sio.on("session_request", namespace=self.namespace)
        async def session_request(sid: Text, data: Optional[Dict]) -> None:
            if data is None:
                data = {}
            if "session_id" not in data or data["session_id"] is None:
                data["session_id"] = uuid.uuid4().hex
            if self.session_persistence:
                if inspect.iscoroutinefunction(sio.enter_room):
                    await sio.enter_room(sid, data["session_id"])
                else:
                    # for backwards compatibility with python-socketio < 5.10.
                    # previously, this function was NOT async.
                    sio.enter_room(sid, data["session_id"])
            await sio.emit("session_confirm", data["session_id"], room=sid)
            logger.debug(f"User {sid} connected to socketIO endpoint.")

        @sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_message(sid: Text, data: Dict) -> None:
            output_channel = DelayedSocketIOOutput(sio, self.bot_message_evt)

            if self.session_persistence:
                if not data.get("session_id"):
                    rasa.shared.utils.io.raise_warning(
                        "A message without a valid session_id "
                        "was received. This message will be "
                        "ignored. Make sure to set a proper "
                        "session id using the "
                        "`session_request` socketIO event."
                    )
                    return
                sender_id = data["session_id"]
            else:
                sender_id = sid

            metadata = data.get(self.metadata_key, {})
            if isinstance(metadata, Text):
                metadata = json.loads(metadata)
            message = UserMessage(
                data.get("message", ""),
                output_channel,
                sender_id,
                input_channel=self.name(),
                metadata=metadata,
            )
            await self.handle_message(on_new_message, sid, data)

        return socketio_webhook
