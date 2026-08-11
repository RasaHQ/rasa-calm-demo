"""Deepdub WebSocket TTS engine for Rasa voice channels.

Protocol reference:
https://docs.deepdub.ai/api-reference/websocket/overview

Deepdub's ``/open`` endpoint accepts one complete ``targetText`` per request
and streams base64-encoded audio chunks until ``isFinished``. That is
non-streaming text input with streaming audio output.

For token-by-token provider streaming, Deepdub documents a separate
Real-Time Streaming API (``/ws`` with ``ctx`` / ``isFinal``); this engine
targets the documented ``/open`` ``text-to-speech`` protocol only.

Interrupt: no in-band cancel is documented for ``/open``; barge-in relies
on Rasa stopping playback locally while provider-side synthesis may continue.
"""

from __future__ import annotations

import base64
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp
import structlog
from aiohttp import ClientTimeout, ClientWSTimeout, WSMsgType

from rasa.core.channels.voice_stream.audio_bytes import (
    L16_24KHZ,
    L16_48KHZ,
    MULAW_8KHZ,
    AudioFormat,
    RasaAudioBytes,
)
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)
from rasa.shared.exceptions import ConnectionException

structlogger = structlog.get_logger()

DEEPDUB_API_KEY_ENV_VAR = "DEEPDUB_API_KEY"
DEFAULT_ENDPOINT = "wss://wsapi.deepdub.ai/open"
DEFAULT_MODEL = "dd-etts-3.0"
DEFAULT_VOICE_PROMPT_ID = "bd1b00bb-be1c-4679-8eaa-0fcbfd4ff773"
DEFAULT_LOCALE = "en-US"


class DeepdubTTSConfig(TTSEngineConfig):
    """Configuration for Deepdub WebSocket TTS.

    Attributes:
        endpoint: WebSocket URL (default ``wss://wsapi.deepdub.ai/open``).
        realtime: Request real-time priority processing when supported.
        tempo: Optional playback speed multiplier (0.5–2.0).
    """

    endpoint: Optional[str] = None
    realtime: Optional[bool] = None
    tempo: Optional[float] = None


class DeepdubTTS(TTSEngine[DeepdubTTSConfig]):
    """Synthesize speech via Deepdub's WebSocket streaming API."""

    required_env_vars = (DEEPDUB_API_KEY_ENV_VAR,)
    required_packages = ("aiohttp",)
    streaming_input = False
    ws: Optional[aiohttp.ClientWebSocketResponse] = None

    @classmethod
    def name(cls) -> str:
        """Return the name identifier for this TTS engine."""
        return "deepdub"

    def __init__(
        self,
        rasa_language: str,
        format: AudioFormat,
        config: Optional[DeepdubTTSConfig] = None,
        additional_languages: Optional[List[str]] = None,
    ):
        super().__init__(rasa_language, format, config, additional_languages or [])
        self.session: Optional[aiohttp.ClientSession] = None

    @staticmethod
    def get_request_headers() -> Dict[str, str]:
        """Build WebSocket handshake headers with the Deepdub API key."""
        api_key = os.environ[DEEPDUB_API_KEY_ENV_VAR]
        return {"x-api-key": api_key}

    async def connect(self, config: Optional[DeepdubTTSConfig] = None) -> None:
        """Open a WebSocket connection to Deepdub TTS."""
        if self.session is None or self.session.closed:
            timeout = ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

        endpoint = self.config.endpoint
        if not endpoint:
            raise ConnectionException("Deepdub endpoint not configured")

        try:
            self.ws = await self.session.ws_connect(
                endpoint,
                headers=self.get_request_headers(),
                timeout=ClientWSTimeout(
                    ws_close=float(self.config.timeout) if self.config.timeout else 30
                ),
            )
        except aiohttp.ClientResponseError as error:
            if error.status == 401:
                message = "Authentication failed. Check DEEPDUB_API_KEY."
            else:
                message = f"Connection to Deepdub TTS failed with status {error.status}"
            structlogger.error(
                "deepdub.connection.failed",
                status_code=error.status,
                error=message,
            )
            raise ConnectionException(message) from error

    async def close_connection(self) -> None:
        """Close the WebSocket and its HTTP session."""
        if self.ws and not self.ws.closed:
            await self.ws.close()
        self.ws = None
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    async def synthesize(
        self, text: str, config: Optional[DeepdubTTSConfig] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        """Send complete text and yield audio chunks until generation finishes."""
        async for audio_chunk in self._synthesize_text(text, config):
            yield audio_chunk

    async def _synthesize_text(
        self, text: str, config: Optional[DeepdubTTSConfig] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        """Send one Deepdub request and yield converted audio chunks."""
        runtime_config = self.config.merge(config)
        async with self._get_engine_lock():
            if not self.ws or self.ws.closed:
                raise TTSError("WebSocket connection not established")

            request = self._build_tts_request(text, runtime_config)
            try:
                await self.ws.send_json(request)
                async for audio_chunk in self._iter_audio_chunks():
                    yield audio_chunk
            except TTSError:
                raise
            except Exception as error:
                structlogger.error("deepdub.synthesize.error", error=str(error))
                raise TTSError(f"Error during Deepdub TTS synthesis: {error}") from error

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        """Wrap raw provider PCM/mulaw bytes as ``RasaAudioBytes``."""
        return RasaAudioBytes(chunk, format=self.audio_format)

    @staticmethod
    def get_default_config(rasa_language: str) -> DeepdubTTSConfig:
        """Return default Deepdub TTS configuration for a Rasa language key."""
        return DeepdubTTSConfig(
            timeout=30,
            endpoint=DEFAULT_ENDPOINT,
            realtime=True,
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    language=DEFAULT_LOCALE,
                    voice=DEFAULT_VOICE_PROMPT_ID,
                    model=DEFAULT_MODEL,
                ),
            },
        )

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "DeepdubTTS":
        """Construct a Deepdub TTS engine from a credentials config dict."""
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=DeepdubTTSConfig.model_validate(config),
            additional_languages=additional_languages,
        )

    def _provider_format_and_sample_rate(self) -> tuple[str, int]:
        """Map Rasa audio format to Deepdub ``format`` and ``sampleRate``."""
        if self.audio_format == MULAW_8KHZ:
            return "mulaw", self.audio_format.sample_rate
        if self.audio_format in (L16_24KHZ, L16_48KHZ):
            return "s16le", self.audio_format.sample_rate
        raise TTSError(f"Unsupported audio format for Deepdub TTS: {self.audio_format}")

    def _build_tts_request(
        self, text: str, config: DeepdubTTSConfig
    ) -> Dict[str, Any]:
        """Build a Deepdub ``text-to-speech`` WebSocket request body."""
        language = self.current_language_config.engine_language_key
        voice = self.current_language_config.voice
        model = self.current_language_config.model
        if not language or not voice or not model:
            raise TTSError(
                "Deepdub TTS requires language (locale), voice (voicePromptId), "
                "and model in language_map."
            )

        provider_format, sample_rate = self._provider_format_and_sample_rate()
        request: Dict[str, Any] = {
            "action": "text-to-speech",
            "model": model,
            "targetText": text,
            "locale": language,
            "voicePromptId": voice,
            "format": provider_format,
            "sampleRate": sample_rate,
        }
        if config.realtime is not None:
            request["realtime"] = config.realtime
        if config.tempo is not None:
            request["tempo"] = config.tempo
        return request

    async def _iter_audio_chunks(self) -> AsyncIterator[RasaAudioBytes]:
        """Consume WebSocket messages until ``isFinished`` or an error."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")

        async for message in self.ws:
            if message.type == WSMsgType.CLOSED:
                structlogger.debug("deepdub.stream_audio.ws_closed")
                return

            if message.type == WSMsgType.ERROR:
                structlogger.error(
                    "deepdub.stream_audio.ws_error", error=str(message.data)
                )
                raise TTSError(f"WebSocket error: {message.data}")

            if message.type != WSMsgType.TEXT:
                continue

            data = message.json()
            if "error" in data:
                error_type = data.get("errorType", "Unknown")
                error_message = data.get("error", "Unknown error")
                structlogger.error(
                    "deepdub.stream_audio.provider_error",
                    error_type=error_type,
                    error=error_message,
                )
                raise TTSError(f"Deepdub TTS error ({error_type}): {error_message}")

            audio_b64 = data.get("data") or ""
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                if audio_bytes:
                    yield self.engine_bytes_to_rasa_audio_bytes(audio_bytes)

            if data.get("isFinished"):
                structlogger.debug("deepdub.stream_audio.finished")
                return
