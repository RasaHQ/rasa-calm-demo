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
    Part,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from a2a.utils import new_task, new_text_artifact
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, Sanic
from uvicorn import Config, Server

logger = logging.getLogger(__name__)


class A2AOutputChannel(OutputChannel):
    """Output channel that pushes Rasa responses to the A2A Event Queue as task artifacts."""

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
        logger.debug(f"[A2A Connector] Sending text artifact: {text}")

        await self.event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=self.task_id,
                context_id=self.context_id,
                artifact=new_text_artifact(
                    name="response",
                    text=text,
                ),
            )
        )


class RasaAgentExecutor(AgentExecutor):
    """Implements A2A AgentExecutor interface, delegating logic to Rasa via on_new_message."""

    def __init__(self, on_new_message: Callable[[UserMessage], Awaitable]):
        self.on_new_message = on_new_message

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Entrypoint from A2A Server when a request comes in."""
        # Enqueue the task object first so the framework has something to track
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        # Signal that processing has started
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        output_channel = A2AOutputChannel(event_queue, context)

        # Use get_user_input() helper; fall back to a safe default if empty
        text = context.get_user_input() or "Hello"
        logger.info(f"[A2A Connector] Received user query: {text}")

        message = UserMessage(
            text=text,
            output_channel=output_channel,
            sender_id=context.context_id,
            input_channel="a2a",
        )

        try:
            await self.on_new_message(message)
        except Exception as e:
            logger.error(f"[A2A Connector] Error handling message in Rasa: {e}")

        # Always signal completion so the orchestrator is never left hanging
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info(f"[A2A Connector] Cancellation requested for task {context.task_id}")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def get_agent_card(public_host: str, port: int) -> AgentCard:
    """Build the AgentCard with a publicly routable URL.

    public_host must be a real hostname or IP (e.g. 'localhost', '127.0.0.1',
    or the machine's LAN IP), never '0.0.0.0'.
    """
    skill = AgentSkill(
        id="list_contacts",
        name="list your contacts",
        description="show your contact list",
        tags=[],
        examples=[
            "List my contacts",
            "What are my contacts?",
            "Show me my contacts",
        ],
    )

    agent_card = AgentCard(
        name="Rasa test A2A Agent",
        description="A Rasa conversational AI agent. Handles contact management tasks: listing contacts, showing contact details, and related queries.",
        url=f"http://{public_host}:{port!s}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    return agent_card


class A2AInputChannel(InputChannel):
    def __init__(self, port: int = 8000, public_host: str = "localhost"):
        self.port = port
        self.listen_host = "0.0.0.0"   # bind to all interfaces
        self.public_host = public_host  # advertised in the agent card URL

    @classmethod
    def name(cls) -> Text:
        return "a2a"

    @classmethod
    def from_credentials(cls, credentials):
        return cls(
            port=credentials.get("port", 8000),
            # Set this to your machine's hostname / LAN IP when the
            # orchestrator runs on a different host.
            public_host=credentials.get("public_host", "localhost"),
        )

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable]
    ) -> Blueprint:
        custom_webhook = Blueprint("a2a_server_hook", __name__)

        @custom_webhook.listener("after_server_start")
        async def start_a2a_background_server(app: Sanic, loop):
            """Initializes the A2A stack and starts Uvicorn on a secondary port."""
            logger.info(
                f"[A2A] Starting A2A Server on {self.listen_host}:{self.port} "
                f"(public URL: http://{self.public_host}:{self.port}/)"
            )

            executor = RasaAgentExecutor(on_new_message)

            request_handler = DefaultRequestHandler(
                agent_executor=executor,
                task_store=InMemoryTaskStore(),
            )
            agent_card = get_agent_card(self.public_host, self.port)

            a2a_starlette_app = A2AStarletteApplication(
                agent_card=agent_card, http_handler=request_handler
            )
            starlette_app = a2a_starlette_app.build()
            config = Config(
                app=starlette_app,
                port=self.port,
                host=self.listen_host,
                log_level="info",
                loop="asyncio",
            )

            server = Server(config=config)
            # Prevent Uvicorn from registering signal handlers that conflict with Sanic
            server.install_signal_handlers = lambda: None

            app.add_task(server.serve())

        return custom_webhook
