import importlib.resources
from typing import Any, Dict, List, Optional, Text

import structlog

import rasa.shared.utils.io
from rasa.dialogue_understanding.commands import (
    CannotHandleCommand,
    Command,
    ErrorCommand,
    SetSlotCommand,
)
from rasa.shared.utils.llm import (
    allowed_values_for_slot,
    llm_factory,
    resolve_model_client_config,
)
from rasa.dialogue_understanding.generator import SingleStepLLMCommandGenerator
from rasa.dialogue_understanding.generator.command_parser import (
    parse_commands as parse_commands_using_command_parsers,
)
from rasa.dialogue_understanding.generator.constants import (
    DEFAULT_LLM_CONFIG,
    FLOW_RETRIEVAL_KEY,
    LLM_CONFIG_KEY,
    USER_INPUT_CONFIG_KEY,
)
from rasa.dialogue_understanding.generator.flow_retrieval import FlowRetrieval
from rasa.dialogue_understanding.generator.llm_based_command_generator import (
    LLMBasedCommandGenerator,
)
from rasa.dialogue_understanding.stack.utils import top_flow_frame
from rasa.dialogue_understanding.utils import (
    add_commands_to_message_parse_data,
    add_prompt_to_message_parse_data,
)
from rasa.engine.graph import ExecutionContext
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.constants import (
    EMBEDDINGS_CONFIG_KEY,
    PROMPT_CONFIG_KEY,
    PROMPT_TEMPLATE_CONFIG_KEY,
    ROUTE_TO_CALM_SLOT,
)
from rasa.shared.core.flows import FlowsList
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.exceptions import ProviderClientAPIException
from rasa.shared.nlu.constants import LLM_COMMANDS, LLM_PROMPT, TEXT
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.utils.io import deep_container_fingerprint
from rasa.shared.utils.llm import (
    get_prompt_template,
    resolve_model_client_config,
    sanitize_message_for_prompt,
    tracker_as_readable_transcript,
    tracker_as_message_list
)
from rasa.utils.beta import BetaNotEnabledException, ensure_beta_feature_is_enabled
from rasa.utils.log_utils import log_llm

COMMAND_PROMPT_FILE_NAME = "command_prompt.jinja2"

DEFAULT_COMMAND_PROMPT_TEMPLATE = importlib.resources.read_text(
    "rasa.dialogue_understanding.generator.single_step",
    "command_prompt_template.jinja2",
)
SINGLE_STEP_LLM_COMMAND_GENERATOR_CONFIG_FILE = "config.json"

structlogger = structlog.get_logger()


@DefaultV1Recipe.register(
    [
        DefaultV1Recipe.ComponentType.COMMAND_GENERATOR,
    ],
    is_trainable=True,
)
class CustomLLMCommandGenerator(SingleStepLLMCommandGenerator):


    def render_template(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        startable_flows: FlowsList,
        all_flows: FlowsList,
        include_conversation_in_prompt: bool = False
    ) -> str:
        """Render the jinja template to create the prompt for the LLM.

        Args:
            message: The current message from the user.
            tracker: The tracker containing the current state of the conversation.
            startable_flows: The flows startable at this point in time by the user.
            all_flows: all flows present in the assistant

        Returns:
            The rendered prompt template.
        """
        # need to make this distinction here because current step of the
        # top_calling_frame would be the call step, but we need the collect step from
        # the called frame. If no call is active calling and called frame are the same.
        top_calling_frame = top_flow_frame(tracker.stack)
        top_called_frame = top_flow_frame(tracker.stack, ignore_call_frames=False)

        top_flow = top_calling_frame.flow(all_flows) if top_calling_frame else None
        current_step = top_called_frame.step(all_flows) if top_called_frame else None

        flow_slots = self.prepare_current_flow_slots_for_template(
            top_flow, current_step, tracker
        )
        current_slot, current_slot_description = self.prepare_current_slot_for_template(
            current_step
        )
        latest_user_message = sanitize_message_for_prompt(message.get(TEXT))

        current_conversation = tracker_as_readable_transcript(tracker)
        current_conversation += f"\nUSER: {latest_user_message}"

        transcript_messages = tracker_as_message_list(tracker)
        transcript_messages.append({"role": "user", "content": sanitize_message_for_prompt(message.get(TEXT))})

        inputs = {
            "available_flows": self.prepare_flows_for_template(
                startable_flows, tracker
            ),
            # "current_conversation": current_conversation,
            "flow_slots": flow_slots,
            "current_flow": top_flow.id if top_flow is not None else None,
            "current_slot": current_slot,
            "current_slot_description": current_slot_description,
            "is_repeat_command_enabled": self.repeat_command_enabled,
        }
        if include_conversation_in_prompt:
            inputs.update({"current_conversation": current_conversation})

        return self.compile_template(self.prompt_template).render(**inputs), transcript_messages

    async def _predict_commands(
        self,
        message: Message,
        flows: FlowsList,
        tracker: Optional[DialogueStateTracker] = None,
    ) -> List[Command]:
        """Predict commands using the LLM.

        Args:
            message: The message from the user.
            flows: The flows available to the user.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The commands generated by the llm.

        Raises:
            ProviderClientAPIException: If API calls raised an error.
        """
        # retrieve flows
        filtered_flows = await self.filter_flows(message, flows, tracker)

        flow_prompt, transcript_messages = self.render_template(message, tracker, filtered_flows, flows)


        action_list = await self.invoke_llm(flow_prompt, transcript_messages)
        # The check for 'None' maintains compatibility with older versions
        # of LLMCommandGenerator. In previous implementations, 'invoke_llm'
        # might return 'None' to indicate a failure to generate actions.
        if action_list is None:
            return [ErrorCommand()]

        log_llm(
            logger=structlogger,
            log_module="SingleStepLLMCommandGenerator",
            log_event="llm_command_generator.predict_commands.actions_generated",
            action_list=action_list,
        )

        commands = self.parse_commands(action_list, tracker, flows)

        self._update_message_parse_data_for_fine_tuning(message, commands, flow_prompt)
        add_commands_to_message_parse_data(
            message, SingleStepLLMCommandGenerator.__name__, commands
        )
        add_prompt_to_message_parse_data(
            message,
            SingleStepLLMCommandGenerator.__name__,
            "command_generator_prompt",
            flow_prompt,
        )

        return commands

    async def invoke_llm(self, prompt: Text, transcript_messages) -> Optional[Text]:
        """Use LLM to generate a response.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            The generated text.

        Raises:
            ProviderClientAPIException if an error during API call.
        """
        end_system_message = \
        """You are given the conversation transcript.
        The user and assistant's messages are available under the 'user' and 'assistant' role.
        Focus on the provided conversation transcript and create an action list with one
        action per line in response to the user's last message in the transcript.
        
        Your action list:"""
        llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)
        try:
            transcript_messages = [
                                      {"role": "system", "content": prompt}] + transcript_messages \
                                  + \
                                  [
                                    # {"role": "system", "content": end_system_message},
                                   {"role": "assistant", "content": "Actions:"}
                                   ]
            log_llm(
                logger=structlogger,
                log_module="SingleStepLLMCommandGenerator",
                log_event="llm_command_generator.predict_commands.prompt_rendered",
                prompt=transcript_messages,
            )
            llm_response = await llm.acompletion_with_system(transcript_messages)
            return llm_response.choices[0]
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("llm_based_command_generator.llm.error", error=e)
            raise ProviderClientAPIException(
                message="LLM call exception", original_exception=e
            )

