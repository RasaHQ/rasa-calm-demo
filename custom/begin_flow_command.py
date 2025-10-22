from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog
from rasa.dialogue_understanding.commands.command_syntax_manager import (
    CommandSyntaxManager,
    CommandSyntaxVersion,
)
from rasa.dialogue_understanding.commands.start_flow_command import StartFlowCommand
from rasa.dialogue_understanding.patterns.continue_interrupted import (
    ContinueInterruptedPatternFlowStackFrame,
)
from rasa.dialogue_understanding.stack.dialogue_stack import DialogueStack
from rasa.dialogue_understanding.stack.frames.flow_stack_frame import UserFlowStackFrame
from rasa.shared.core.events import Event
from rasa.shared.core.trackers import DialogueStateTracker

structlogger = structlog.get_logger()


@dataclass
class BeginFlowCommand(StartFlowCommand):
    """A command to begin a flow."""

    flow: str

    @classmethod
    def command(cls) -> str:
        """Returns the command type."""
        return "begin flow"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BeginFlowCommand:
        """Converts the dictionary to a command.

        Returns:
            The converted dictionary.
        """
        try:
            return BeginFlowCommand(flow=data["flow"])
        except KeyError as e:
            raise ValueError(
                f"Missing parameter '{e}' while parsing BeginFlowCommand."
            ) from e

    def __hash__(self) -> int:
        return hash(self.flow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BeginFlowCommand):
            return False

        return other.flow == self.flow

    def to_dsl(self) -> str:
        """Converts the command to a DSL string."""
        mapper = {
            CommandSyntaxVersion.v1: f"BeginFlow({self.flow})",
            CommandSyntaxVersion.v2: f"begin_flow {self.flow}",
        }
        return mapper.get(
            CommandSyntaxManager.get_syntax_version(),
            mapper[CommandSyntaxManager.get_default_syntax_version()],
        )

    @classmethod
    def from_dsl(cls, match: re.Match, **kwargs: Any) -> Optional[BeginFlowCommand]:
        """Converts the DSL string to a command."""
        return BeginFlowCommand(flow=str(match.group(1).strip()))

    @staticmethod
    def regex_pattern() -> str:
        mapper = {
            CommandSyntaxVersion.v1: r"BeginFlow\(['\"]?([a-zA-Z0-9_-]+)['\"]?\)",
            CommandSyntaxVersion.v2: r"^[^\w]*begin_flow ['\"]?([a-zA-Z0-9_-]+)['\"]?",
            CommandSyntaxVersion.v3: (r"""^[\s\W\d]*begin_flow ['"`]?([a-zA-Z0-9_-]+)['"`]*""")
        }
        return mapper.get(
            CommandSyntaxManager.get_syntax_version(),
            mapper[CommandSyntaxManager.get_default_syntax_version()],
        )
