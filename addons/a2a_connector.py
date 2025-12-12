import logging
import uuid
from typing import Any, Awaitable, Callable, Text

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    Part,
    Role,
    TextPart,
)
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, Sanic
from starlette.applications import Starlette
from uvicorn import Config, Server

logger = logging.getLogger(__name__)


class A2AOutputChannel(OutputChannel):
    """Output channel that pushes Rasa responses directly to the A2A Event Queue."""

    def __init__(self, event_queue: EventQueue, context: RequestContext):
        super().__init__()
        self.event_queue = event_queue
        self.task_id = context.task_id
        self.context_id = context.context_id

    @classmethod
    def name(cls) -> Text:
        return "a2a"

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Called by Rasa when the bot sends a text message."""
        logger.debug(f"[A2A Connector] Sending text: {text}")

        parts = [Part(root=TextPart(text=text))]
        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=parts,
            context_id=self.context_id,
            task_id=self.task_id,
        )
        await self.event_queue.enqueue_event(message)


class RasaAgentExecutor(AgentExecutor):
    """Implements A2A AgentExecutor interface but delegates logic to Rasa via on_new_message."""

    def __init__(self, on_new_message: Callable[[UserMessage], Awaitable[None]]):
        self.on_new_message = on_new_message

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Entrypoint from A2A Server when a request comes in."""
        # Setup Output Channel
        output_channel = A2AOutputChannel(event_queue, context)

        # Parse Input
        text = "Hello"  # Fallback
        if context.message and context.message.parts and len(context.message.parts) > 0:
            first_part = context.message.parts[0]
            if isinstance(first_part.root, TextPart):
                text = first_part.root.text
        logger.info(f"[A2A Connector] Received user query: {text}")

        # Construct UserMessage and pass our custom OutputChannel
        message = UserMessage(
            text=text,
            output_channel=output_channel,
            sender_id=context.context_id,
            input_channel="a2a",
        )

        # Invoke Rasa
        # Any responses generated during this call will flow through A2AOutputChannel.send_text_message
        try:
            await self.on_new_message(message)
        except Exception as e:
            logger.error(f"Error handling message in Rasa: {e}")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info(f"Cancellation requested for task {context.task_id}")


def get_agent_card(host: str, port: int) -> AgentCard:
    skill = AgentSkill(
        id="some_skill_id",
        name="Some Skill Name",
        description="TODO",
        tags=[],
        examples=[
            "Example 1",
        ],
    )

    agent_card = AgentCard(
        name="Rasa test A2A Agent",
        description="A Rasa agent bridged to A2A",
        url=f"http://{host}:{port!s}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    return agent_card


class A2AInputChannel(InputChannel):
    def __init__(self, port: int = 8000):
        self.port = port
        self.host = "0.0.0.0"

    @classmethod
    def name(cls) -> Text:
        return "a2a"

    @classmethod
    def from_credentials(cls, credentials):
        return cls(
            port=credentials.get("port", 8000),
        )

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        custom_webhook = Blueprint("a2a_server_hook", __name__)

        @custom_webhook.listener("after_server_start")
        async def start_a2a_background_server(app: Sanic, loop):
            """This runs ONCE when Rasa starts.
            It initializes the A2A stack and starts Uvicorn on a secondary port.
            """
            logger.info(f"[A2A] Initializing A2A Server on port {self.port}...")

            # Initialize A2A Agent Executor with the callback we got from Rasa
            executor = RasaAgentExecutor(on_new_message)

            # Setup A2A Stack
            request_handler = DefaultRequestHandler(
                agent_executor=executor,
                task_store=InMemoryTaskStore(),  # or generic store
            )
            agent_card = get_agent_card(self.host, self.port)

            a2a_starlette_app = A2AStarletteApplication(
                agent_card=agent_card, http_handler=request_handler
            )
            routes = a2a_starlette_app.routes()
            starlette_app = Starlette(routes=routes)
            config = Config(
                app=starlette_app,
                port=self.port,
                host=self.host,
                log_level="info",
                loop="asyncio",  # Reuse the running asyncio loop context
            )

            server = Server(config=config)
            # Important: disable signal handlers so Uvicorn doesn't fight Sanic
            server.install_signal_handlers = lambda: None

            # Run as background task
            # We use app.add_task to schedule it on the MAIN loop
            app.add_task(server.serve())

        return custom_webhook
