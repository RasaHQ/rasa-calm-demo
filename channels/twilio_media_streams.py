import logging
import websockets
from typing import Text, Callable, Awaitable, List, Any, Dict, Optional
from sanic import Blueprint, response, Websocket
from sanic.request import Request
from sanic.response import HTTPResponse

from twilio.twiml.voice_response import VoiceResponse, Connect

import rasa.core.channels.channel
from rasa.core.channels.channel import (
    InputChannel,

    UserMessage,
)
from rasa.core.channels import SocketIOInput
from socketio import AsyncServer
from sanic import Blueprint, response, Sanic

logger = logging.getLogger(__name__)

class TwilioVoiceInput(InputChannel):
    """Input channel for Twilio Voice."""

    @classmethod
    def name(cls) -> Text:
        """Name of channel."""
        return "twilio_voice"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        """Load custom configurations."""
        credentials = credentials or {}

        return cls(
            credentials.get("initial_prompt", "hello"),
            credentials.get(
                "reprompt_fallback_phrase",
                "I'm sorry I didn't get that could you rephrase.",
            ),
            credentials.get("server_url", "0.0.0.0")
        )
    def __init__(
        self,
        initial_prompt: Optional[Text],
        reprompt_fallback_phrase: Optional[Text],
        server_url: Optional[Text]
        
    ) -> None:
        """Creates a connection to Twilio voice.

        Args:
            initial_prompt: text to use to prompt a conversation when call is answered.
            reprompt_fallback_phrase: phrase to use if no user response.
            assistant_voice: name of the assistant voice to use.
            speech_timeout: how long to pause when user finished speaking.
            speech_model: type of transcription model to use from Twilio.
            enhanced: toggle to use Twilio's premium speech transcription model.
        """
        self.initial_prompt = initial_prompt
        self.reprompt_fallback_phrase = reprompt_fallback_phrase
        self.server_url = server_url
        
    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        """Defines endpoints for Twilio voice channel."""
        twilio_voice_webhook = Blueprint("Twilio_voice_webhook", __name__)

        @twilio_voice_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @twilio_voice_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:
            voice_response = VoiceResponse()
            voice_response.say(self.initial_prompt)
            start = Connect()
            start.stream(url=f"wss://{self.server_url}/webhooks/twilio_web_sockets/websocket")
            voice_response.append(start)
            voice_response.pause(10)
            
            return response.text(str(voice_response), content_type='text/xml')
        return twilio_voice_webhook


class TwilioWebSockets(InputChannel):
    """A socket.io input channel."""

    @classmethod
    def name(cls) -> Text:
        return "twilio_web_sockets"

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
    ):
        """Creates a ``SocketIOInput`` object."""
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.sio: Optional[AsyncServer] = None
        self.metadata_key = metadata_key

        self.jwt_key = jwt_key
        self.jwt_algorithm = jwt_method

    

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        """Defines a Sanic blueprint."""
        socketio_webhook = Blueprint(
            "socketio_webhook", __name__
        )

        
        @socketio_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})
        
        @socketio_webhook.websocket("/websocket")
        async def handle_message(request: Request, ws: Websocket) -> None:
            async for message in ws:
                print(message)

        
            
        return socketio_webhook
