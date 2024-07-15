import logging
import asyncio
import asyncio
import websockets
import json
import base64
import random

from typing import Text, Callable, Awaitable, List, Any, Dict, Optional
from sanic import Blueprint, response, Websocket
from sanic.request import Request
from sanic.response import HTTPResponse

from twilio.twiml.voice_response import VoiceResponse, Connect
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from rasa.core.channels.channel import (
    InputChannel,
    OutputChannel,
    UserMessage,
)


logger = logging.getLogger(__name__)

FILLER_TEXT = [
    "okay, let me check",
    "sure, wait a second please",
    "okay, let me take a look",
    "ok",
    "understood, let me check",
]


def eleven_labs_encoded_stream(client: ElevenLabs, text: str):
    from datetime import datetime
    start_time = datetime.now()
    response = client.text_to_speech.convert(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        enable_logging=True,  # Adam pre-made voice
        optimize_streaming_latency="0",
        output_format="ulaw_8000",
        text=text,
        model_id="eleven_turbo_v2",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
        ),
    )

    print("Streaming audio data...")
    audio_stream = b""
    for chunk in response:
        if chunk:
            audio_stream += chunk
    encoded_stream = base64.b64encode(audio_stream).decode("utf-8")
    end_time = datetime.now()
    print('Duration: {}'.format(end_time - start_time))
    return encoded_stream


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
            credentials.get("server_url", "0.0.0.0"),
        )

    def __init__(
        self,
        initial_prompt: Optional[Text],
        reprompt_fallback_phrase: Optional[Text],
        server_url: Optional[Text],
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
            start.stream(
                url=f"wss://{self.server_url}/webhooks/twilio_web_sockets/websocket"
            )
            voice_response.append(start)
            voice_response.pause(10)

            return response.text(str(voice_response), content_type="text/xml")

        return twilio_voice_webhook


class TwilioWebSocketsOutput(OutputChannel):
    @classmethod
    def name(cls) -> Text:
        return "twilio_web_sockets"

    def __init__(self, ws, streamSID, eleven_labs_client) -> None:
        self.ws = ws
        self.inbox = asyncio.Queue()
        self.client = eleven_labs_client
        self.streamSID = streamSID

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""
        for message_part in text.strip().split("\n\n"):
            encoded_stream = eleven_labs_encoded_stream(self.client, message_part)
            message = json.dumps(
                {
                    "event": "media",
                    "streamSid": self.streamSID,
                    "media": {
                        "payload": encoded_stream,
                    },
                }
            )

            await self.ws.send(message)


class TwilioWebSockets(InputChannel):
    """A socket.io input channel."""

    @classmethod
    def name(cls) -> Text:
        return "twilio_web_sockets"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        credentials = credentials or {}
        return cls()

    def __init__(self):
        """Creates a ``SocketIOInput`` object."""
        self.outbox = asyncio.Queue()
        self.sender_id = None
        self.client = ElevenLabs(
            api_key="ELEVEN_LABS_API_KEY",  # Defaults to ELEVEN_API_KEY
        )

    def deepgram_connect(self):
        extra_headers = {
            "Authorization": "Token DEEPGRAM_API_KEY"
        }
        deepgram_ws = websockets.connect(
            "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&endpointing=true",
            extra_headers=extra_headers,
        )
        return deepgram_ws

    async def proxy(self, client_ws, on_new_message):
        outbox = asyncio.Queue()

        print("started proxy")

        audio_cursor = 0.0
        async with self.deepgram_connect() as deepgram_ws:

            async def deepgram_sender(deepgram_ws):
                print("started deepgram sender")
                while True:
                    chunk = await outbox.get()
                    await deepgram_ws.send(chunk)
                print("finished deepgram sender")

            async def deepgram_receiver(deepgram_ws, client_ws):
                print("started deepgram receiver")
                nonlocal audio_cursor
                async for message in deepgram_ws:
                    try:
                        dg_json = json.loads(message)
                        try:
                            if dg_json["is_final"] == True:
                                transcript = dg_json["channel"]["alternatives"][0][
                                    "transcript"
                                ]
                                if transcript:
                                    filler_text = random.sample(FILLER_TEXT, 1)
                                    encoded_stream = eleven_labs_encoded_stream(
                                        self.client, filler_text[0]
                                    )
                                    filler_message = json.dumps(
                                        {
                                            "event": "media",
                                            "streamSid": self.sender_id,
                                            "media": {
                                                "payload": encoded_stream,
                                            },
                                        }
                                    )
                                    await client_ws.send(filler_message)
                                    
                                    output_channel = TwilioWebSocketsOutput(
                                        client_ws, self.sender_id, self.client
                                    )
                                    message = UserMessage(
                                        transcript,
                                        output_channel,
                                        "default",
                                        input_channel="twilio_web_sockets",
                                        metadata={},
                                        filler_text= filler_text
                                    )
                                    await on_new_message(message)
                                    
                                else:
                                    print("empty transcript")
                        except:
                            print("did not receive a standard streaming result")
                            continue
                    except:
                        print("was not able to parse deepgram response as json")
                        continue
                print("finished deepgram receiver")

            async def client_receiver(client_ws):
                print("started client receiver")
                nonlocal audio_cursor

                # we will use a buffer of 20 messages (20 * 160 bytes, 0.4 seconds) to improve throughput performance
                # NOTE: twilio seems to consistently send media messages of 160 bytes
                BUFFER_SIZE = 20 * 160
                buffer = bytearray(b"")
                empty_byte_received = False
                async for message in client_ws:
                    try:

                        data = json.loads(message)
                        if data["event"] in ("connected", "start"):
                            print("Media WS: Received event connected or start")
                            continue
                        if data["event"] == "media":
                            self.sender_id = data["streamSid"]
                            media = data["media"]
                            chunk = base64.b64decode(media["payload"])
                            time_increment = len(chunk) / 8000.0
                            audio_cursor += time_increment
                            buffer.extend(chunk)
                            if chunk == b"":
                                empty_byte_received = True
                        if data["event"] == "stop":
                            print("Media WS: Received event stop")
                            break

                        # check if our buffer is ready to send to our outbox (and, thus, then to deepgram)
                        if len(buffer) >= BUFFER_SIZE or empty_byte_received:
                            outbox.put_nowait(buffer)
                            buffer = bytearray(b"")
                    except:
                        print("message from client not formatted correctly, bailing")
                        break

                # if the empty byte was received, the async for loop should end, and we should here forward the empty byte to deepgram
                # or, if the empty byte was not received, but the WS connection to the client (twilio) died, then the async for loop will end and we should forward an empty byte to deepgram
                outbox.put_nowait(b"")
                print("finished client receiver")

            await asyncio.wait(
                [
                    asyncio.ensure_future(deepgram_sender(deepgram_ws)),
                    asyncio.ensure_future(deepgram_receiver(deepgram_ws, client_ws)),
                    asyncio.ensure_future(client_receiver(client_ws)),
                ]
            )

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        """Defines a Sanic blueprint."""
        socketio_webhook = Blueprint("socketio_webhook", __name__)

        @socketio_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @socketio_webhook.websocket("/websocket")
        async def handle_message(request: Request, ws: Websocket) -> None:

            await self.proxy(ws, on_new_message)

        return socketio_webhook
