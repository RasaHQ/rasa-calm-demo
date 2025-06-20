from typing import List, Optional

import structlog
from rasa.dialogue_understanding.commands import Command, StartFlowCommand
from rasa.dialogue_understanding.generator import SearchReadyLLMCommandGenerator
from rasa.dialogue_understanding.generator.command_parser import (
    parse_commands as parse_commands_using_command_parsers,
)
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.shared.core.flows import FlowsList
from rasa.shared.core.trackers import DialogueStateTracker

from .begin_flow_command import BeginFlowCommand

structlogger = structlog.get_logger()


@DefaultV1Recipe.register(
    [DefaultV1Recipe.ComponentType.COMMAND_GENERATOR],
    is_trainable=True,
)
class CustomSearchReadyLLMCommandGenerator(SearchReadyLLMCommandGenerator):
    @classmethod
    def parse_commands(
        cls, actions: Optional[str], tracker: DialogueStateTracker, flows: FlowsList
    ) -> List[Command]:
        """Parse the actions returned by the llm into intent and entities.

        Args:
            actions: The actions returned by the llm.
            tracker: The tracker containing the current state of the conversation.
            flows: the list of flows

        Returns:
            The parsed commands.
        """
        commands = parse_commands_using_command_parsers(
            actions, flows, False, [BeginFlowCommand], [StartFlowCommand]
        )

        if not commands:
            structlogger.debug(
                f"{cls.__class__.__name__}.parse_commands",
                message="No commands were parsed from the LLM actions.",
                actions=actions,
            )
        return commands
