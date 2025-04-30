from typing import List, Optional
import structlog

from rasa.dialogue_understanding.commands import Command, CancelFlowCommand
from rasa.dialogue_understanding.generator.command_parser import (
    parse_commands as parse_commands_using_command_parsers,
)
from rasa.dialogue_understanding.generator.single_step.compact_llm_command_generator import CompactLLMCommandGenerator
from rasa.shared.core.flows import FlowsList
from rasa.shared.core.trackers import DialogueStateTracker
from custom_command_generator.modified_cancel_flow_command import ModifiedCancelFlowCommand


structlogger = structlog.get_logger()

class CustomCommandGenerator(CompactLLMCommandGenerator):

    @classmethod
    def parse_commands(
        cls, actions: Optional[str], tracker: DialogueStateTracker, flows: FlowsList
    ) -> List[Command]:
        commands = parse_commands_using_command_parsers(actions, flows, additional_commands=[ModifiedCancelFlowCommand], default_commands_to_remove=[CancelFlowCommand])
        if not commands:
            structlogger.warning(
                f"{cls.__name__}.parse_commands",
                message="No commands were parsed from the LLM actions.",
                actions=actions,
            )

        return commands