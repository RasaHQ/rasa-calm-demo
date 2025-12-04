"""
Simple WebSocket Channel for Rasa without Streaming Support
"""

import inspect
import json
import logging
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Text, Any, Callable, Awaitable


from rasa.core.channels.channel import (
    InputChannel,
    OutputChannel,
    UserMessage,
)

logger = logging.getLogger(__name__)


class WebSocketOutputChannel(OutputChannel):
    """Simple WebSocket output channel with streaming support."""

    def __init__(self, websocket):
        super().__init__()
        self.websocket = websocket
        self.streaming_response_sent = False

    @classmethod
    def name(cls) -> Text:
        return "websocket_stream"

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a text message. Skip if already streamed."""
        if self.streaming_response_sent:
            # Avoid sending duplicate messages after streaming
            # Reset the flag for future messages
            self.streaming_response_sent = False
            return

        await self.websocket.send(
            json.dumps({"type": "text", "text": text, "recipient_id": recipient_id})
        )

    # Streaming methods for generative responses
    async def send_response_chunk_start(
        self, recipient_id: Text, **kwargs: Any
    ) -> None:
        """Initialize streaming for a generative response."""
        await self.websocket.send(
            json.dumps({"type": "stream_start", "recipient_id": recipient_id})
        )

    async def send_response_chunk(
        self, recipient_id: Text, chunk: Text, **kwargs: Any
    ) -> None:
        """Send a chunk of the generative response."""
        await self.websocket.send(
            json.dumps(
                {"type": "stream_chunk", "recipient_id": recipient_id, "chunk": chunk}
            )
        )

    async def send_response_chunk_end(self, recipient_id: Text, **kwargs: Any) -> None:
        """Finalize the streaming response."""
        await self.websocket.send(
            json.dumps({"type": "stream_end", "recipient_id": recipient_id})
        )
        # Mark that the streaming response has been sent
        self.streaming_response_sent = True


class WebSocketChannel(InputChannel):
    """Simple WebSocket channel using aiohttp."""

    def __init__(self):
        self.websockets = set()

    @classmethod
    def name(cls) -> Text:
        return "websocket"

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        """Create Sanic blueprint with WebSocket endpoint."""

        websocket_webhook = Blueprint(
            "websocket_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        @websocket_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @websocket_webhook.websocket("/ws")
        async def websocket_handler(request, ws):
            """Handle WebSocket connections and messages."""
            self.websockets.add(ws)
            logger.info(f"WebSocket client connected")

            try:
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        text = data.get("message", "")
                        sender_id = data.get("sender", f"ws_{id(ws)}")
                        metadata = data.get("metadata", {})

                        if text:
                            output_channel = WebSocketOutputChannel(ws)
                            user_message = UserMessage(
                                text=text,
                                output_channel=output_channel,
                                sender_id=sender_id,
                                input_channel=self.name(),
                                metadata=metadata,
                            )
                            await on_new_message(user_message)

                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON received")
                    except Exception as e:
                        logger.exception(f"Error processing message: {e}")

            finally:
                self.websockets.discard(ws)
                logger.debug("WebSocket client disconnected")

        return websocket_webhook
