"""
Custom Input Channel for Rasa
"""

import inspect
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Text, Dict, Any, Optional, Callable, Awaitable

from rasa.core.channels.channel import (
    InputChannel,
    CollectingOutputChannel,
    UserMessage,
)


class MyIO(InputChannel):
    def name(self) -> Text:
        """Name of your custom channel."""
        return "myio"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        """Create an instance of the input channel from user-provided credentials."""
        if not credentials:
            cls.raise_missing_credentials_exception()

        username = credentials.get("username")
        password = credentials.get("password")

        # Overwrite the constructor to pass the credentials if needed
        return cls()

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @custom_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:
            sender_id = request.json.get("sender")  # method to get sender_id
            text = request.json.get("text")  # method to fetch text
            metadata = self.get_metadata(request)  # method to get metadata

            collector = CollectingOutputChannel()

            # include exception handling

            await on_new_message(
                UserMessage(
                    text,
                    collector,
                    sender_id,
                    input_channel=self.name(),
                    metadata=metadata,
                )
            )

            return response.json(
                {
                    "recipient_id": sender_id,
                    "messages": collector.messages,
                    "tracker_state": collector.tracker_state,
                }
            )

        return custom_webhook
