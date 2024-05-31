import importlib.resources
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Union, Text

import structlog
from jinja2 import Template

from rasa.dialogue_understanding.commands import (
    Command,
    ErrorCommand,
    SetSlotCommand,
    CancelFlowCommand,
    StartFlowCommand,
    ClarifyCommand,
    CannotHandleCommand,
)
from rasa.dialogue_understanding.generator import CommandGenerator
from rasa.dialogue_understanding.stack.frames import UserFlowStackFrame
from rasa.dialogue_understanding.stack.utils import (
    top_flow_frame,
    top_user_flow_frame,
    user_flows_on_the_stack,
)
from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.core.events import Event
from rasa.shared.core.flows import FlowStep, Flow, FlowsList
from rasa.shared.core.flows.steps.collect import CollectInformationFlowStep
from rasa.shared.core.slots import (
    BooleanSlot,
    CategoricalSlot,
    Slot,
)
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.exceptions import FileIOException
from rasa.shared.nlu.constants import TEXT
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.utils.io import deep_container_fingerprint
import rasa.shared.utils.io
from rasa.shared.utils.llm import (
    DEFAULT_OPENAI_CHAT_MODEL_NAME_ADVANCED,
    DEFAULT_OPENAI_MAX_GENERATED_TOKENS,
    get_prompt_template,
    llm_factory,
    tracker_as_readable_transcript,
    sanitize_message_for_prompt,
)

# multistep template keys
START_OR_END_FLOW_KEY = "start_or_end_flow"
FILL_SLOTS_KEY = "fill_slots"

# multistep template file names
START_OR_END_FLOWS_PROMPT_FILE_NAME = "start_or_end_flows_prompt.jinja2"
FILL_SLOTS_PROMPT_FILE_NAME = "fill_slots_prompt.jinja2"

# multistep templates
DEFAULT_START_OR_END_FLOWS_TEMPLATE = importlib.resources.read_text(
    "custom_components", "start_or_end_flows_prompt.jinja2"
).strip()
DEFAULT_FILL_SLOTS_TEMPLATE = importlib.resources.read_text(
    "custom_components", "fill_slots_prompt.jinja2"
).strip()

# dictionary of template names and associated file names and default values
PROMPT_TEMPLATES = {
    START_OR_END_FLOW_KEY: (
        START_OR_END_FLOWS_PROMPT_FILE_NAME,
        DEFAULT_START_OR_END_FLOWS_TEMPLATE,
    ),
    FILL_SLOTS_KEY: (
        FILL_SLOTS_PROMPT_FILE_NAME,
        DEFAULT_FILL_SLOTS_TEMPLATE,
    ),
}

DEFAULT_LLM_CONFIG = {
    "_type": "openai",
    "request_timeout": 7,
    "temperature": 0.0,
    "model_name": DEFAULT_OPENAI_CHAT_MODEL_NAME_ADVANCED,
    "max_tokens": DEFAULT_OPENAI_MAX_GENERATED_TOKENS,
}

LLM_CONFIG_KEY = "llm"
USER_INPUT_CONFIG_KEY = "user_input"
FILE_PATH_KEY = "file_path"


structlogger = structlog.get_logger()


@dataclass
class ChangeFlowCommand(Command):
    """A command to indicate a change of flows was requested by the command
    generator."""

    @classmethod
    def command(cls) -> str:
        """Returns the command type."""
        return "change_flow"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeFlowCommand":
        """Converts the dictionary to a command.

        Returns:
            The converted dictionary.
        """
        return ChangeFlowCommand()

    def run_command_on_tracker(
        self,
        tracker: DialogueStateTracker,
        all_flows: FlowsList,
        original_tracker: DialogueStateTracker,
    ) -> List[Event]:
        # the change flow command is not actually pushing anything to the tracker,
        # but it is predicted by the MultiStepLLMCommandGenerator and used internally
        return []



@DefaultV1Recipe.register(
    [
        DefaultV1Recipe.ComponentType.COMMAND_GENERATOR,
    ],
    is_trainable=True,
)
class MultiStepLLMCommandGenerator(GraphComponent, CommandGenerator):
    """An multi step command generator using LLM."""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """The component's default config (see parent class for full docstring)."""
        return {
            "prompts": {},
            USER_INPUT_CONFIG_KEY: None,
            LLM_CONFIG_KEY: None,
        }

    def __init__(
        self,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        prompt_templates: Optional[Dict[Text, Optional[Text]]] = None,
    ) -> None:
        super().__init__(config)
        self.config = {**self.get_default_config(), **config}
        print(self.config)
        self._prompts: Dict[Text, Optional[Text]] = {
            START_OR_END_FLOW_KEY: None,
            FILL_SLOTS_KEY: None,
        }
        self._init_prompt_templates(prompt_templates)
        self._model_storage = model_storage
        self._resource = resource

    @property
    def start_or_end_flows_prompt(self) -> Optional[Text]:
        return self._prompts[START_OR_END_FLOW_KEY]

    @property
    def fill_slots_prompt(self) -> Optional[Text]:
        return self._prompts[FILL_SLOTS_KEY]

    def _init_prompt_templates(self, prompt_templates: Dict[Text, Any]) -> None:
        for key in self._prompts.keys():
            _, default_template = PROMPT_TEMPLATES[key]
            self._prompts[key] = self._resolve_prompt_template(
                prompt_templates, self.config, key, default_template
            )

    @staticmethod
    def _resolve_prompt_template(
        prompt_templates: Optional[Dict[Text, Optional[Text]]],
        config: Dict[Text, Any],
        key: Text,
        default_value: Text,
    ) -> Text:
        """Determines and retrieves a prompt template for a specific step in the
        multistep command generator process using a given key. If the prompt
        associated with the key is missing in both the `prompt_templates` and the
        `config`, this method defaults to using a predefined prompt template. Each key
        is uniquely associated with a distinct step of the command generation process.

        Args:
            prompt_templates: A dictionary of override templates.
            config: The components config that may contain the file paths to the prompt
            templates.
            key: The key for the desired template.
            default_value: The default template to use if no other is found.

        Returns:
            Prompt template.
        """

        if (
            prompt_templates is not None
            and key in prompt_templates
            and prompt_templates[key] is not None
        ):
            return prompt_templates[key]  # type: ignore[return-value]
        return get_prompt_template(
            config.get("prompts", {}).get(key, {}).get(FILE_PATH_KEY),
            default_value,
        )

    @classmethod
    def create(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "MultiStepLLMCommandGenerator":
        """Creates a new untrained component (see parent class for full docstring)."""
        return cls(config, model_storage, resource)

    @classmethod
    def load(
        cls,
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
        **kwargs: Any,
    ) -> "MultiStepLLMCommandGenerator":
        """Loads trained component (see parent class for full docstring)."""
        prompts = cls._load_prompt_templates(model_storage, resource)
        return cls(config, model_storage, resource, prompts)

    @staticmethod
    def _load_prompt_templates(
        model_storage: ModelStorage, resource: Resource
    ) -> Dict[Text, Text]:
        """Loads persisted prompt templates from the model storage. If a prompt template
        cannot be loaded, default value is used.
        """
        prompts = {}
        for key, (file_name, default_value) in PROMPT_TEMPLATES.items():
            try:
                with model_storage.read_from(resource) as path:
                    prompts[key] = rasa.shared.utils.io.read_file(path / file_name)
            except (FileNotFoundError, FileIOException) as e:
                structlogger.warning(
                    "llm_command_generator.load.failed", error=e, resource=resource.name
                )
                prompts[key] = default_value
        return prompts

    def train(self, training_data: TrainingData) -> Resource:
        """Train the intent classifier on a data set."""
        self.persist()
        return self._resource

    def persist(self) -> None:
        """Persist this component to disk for future loading."""
        self._persist_prompt_templates()

    def _persist_prompt_templates(self) -> None:
        """Persist the prompt templates to disk for future loading."""
        with self._model_storage.write_to(self._resource) as path:
            for key, template in self._prompts.items():
                file_name, _ = PROMPT_TEMPLATES[key]
                file_path = path / file_name
                rasa.shared.utils.io.write_text_file(template, file_path)

    def _has_active_flow(self, stack):
        from rasa.dialogue_understanding.stack.utils import top_flow_frame

        top_relevant_frame = top_flow_frame(stack)
        return bool(top_relevant_frame and top_relevant_frame.flow_id)

    async def predict_commands(
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
        """

        if tracker is None or flows.is_empty():
            # cannot do anything if there are no flows or no tracker
            return []

        if self._has_active_flow(tracker.stack):
            commands_from_active_flow = await self.predict_commands_for_active_flow(
                message, tracker, flows
            )
        else:
            commands_from_active_flow = []

        contains_change_flow_command = any(
            isinstance(command, ChangeFlowCommand)
            for command in commands_from_active_flow
        )
        change_flows = not commands_from_active_flow or contains_change_flow_command

        if change_flows:
            commands_for_starting_or_ending_flows = (
                await self.predict_commands_for_starting_and_ending_flows(
                    message,
                    tracker,
                    flows,
                )
            )
        else:
            commands_for_starting_or_ending_flows = []

        if contains_change_flow_command:
            commands_from_active_flow.pop(
                commands_from_active_flow.index(ChangeFlowCommand())
            )

        started_flows = FlowsList(
            [
                flow
                for command in commands_for_starting_or_ending_flows
                if (
                    isinstance(command, StartFlowCommand)
                    and (flow := flows.flow_by_id(command.flow)) is not None
                )
            ]
        )

        commands_for_newly_started_flows = (
            await self.predict_commands_for_newly_started_flows(
                message, tracker, started_flows
            )
        )

        commands = list(
            set(
                commands_from_active_flow
                + commands_for_starting_or_ending_flows
                + commands_for_newly_started_flows
            )
        )
        # do not refine slots as it does not work well
        # commands = await self.refine_commands(commands, tracker, flows, message)
        structlogger.debug(
            "multi_step_llm_command_generator" ".predict_commands" ".finished",
            commands=commands,
        )

        return commands

    async def predict_commands_for_active_flow(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> List[Command]:
        """Predicts set slots commands for currently active flow."""

        inputs = self.prepare_inputs(message, tracker, flows)

        if inputs["current_flow"] is None:
            return []

        prompt = Template(self.fill_slots_prompt).render(**inputs).strip()
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_active_flow"
            ".prompt_rendered",
            prompt=prompt,
        )

        actions = await self._invoke_llm(prompt)
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_active_flow"
            ".actions_generated",
            action_list=actions,
        )
        if actions is None:
            return []

        commands = self.parse_commands(actions, tracker, flows)
        return commands

    async def predict_commands_for_starting_and_ending_flows(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> List[Command]:
        """Predicts commands for starting and canceling flows."""

        inputs = self.prepare_inputs(message, tracker, flows, 2)
        prompt = Template(self.start_or_end_flows_prompt).render(**inputs).strip()
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_starting_and_ending_flows"
            ".prompt_rendered",
            prompt=prompt,
        )

        actions = await self._invoke_llm(prompt)
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_starting_and_ending_flows"
            ".actions_generated",
            action_list=actions,
        )
        if actions is None:
            return []

        commands = self.parse_commands(actions, tracker, flows, True)
        # filter out flows that are already started and active
        commands = self._filter_redundant_start_flow_commands(tracker, commands)

        return commands

    @staticmethod
    def _filter_redundant_start_flow_commands(
        tracker: DialogueStateTracker, commands: List[Command]
    ) -> List[Command]:
        """Filters out StartFlowCommand commands for flows that are already active,
        based on the current tracker state.
        """
        frames = tracker.stack.frames
        active_user_flows = {
            frame.flow_id for frame in frames if isinstance(frame, UserFlowStackFrame)
        }
        commands = [
            command
            for command in commands
            if not (
                isinstance(command, StartFlowCommand)
                and command.flow in active_user_flows
            )
        ]
        return commands

    async def predict_commands_for_newly_started_flows(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> List[Command]:
        """Predict set slot commands for newly started flows."""
        commands_for_newly_started_flows = []
        for flow in flows:
            commands_for_newly_started_flows += (
                await self.predict_commands_for_newly_started_flow(
                    flow, message, tracker, flows
                )
            )
        return commands_for_newly_started_flows

    async def predict_commands_for_newly_started_flow(
        self,
        flow: Flow,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> List[Command]:

        inputs = self.prepare_inputs_for_single_flow(
            message, tracker, flow, max_turns=20
        )

        if len(inputs["flow_slots"]) == 0:
            # return empty if the newly started flow does not have any slots
            return []

        prompt = Template(self.fill_slots_prompt).render(**inputs)
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_newly_started_flow"
            ".prompt_rendered",
            flow=flow.id,
            prompt=prompt,
        )

        actions = await self._invoke_llm(prompt)
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_newly_started_flow"
            ".actions_generated",
            flow=flow.id,
            action_list=actions,
        )
        if actions is None:
            return []

        commands = self.parse_commands(actions, tracker, flows)

        # filter out all commands that unset values for newly started flow
        commands = [
            command
            for command in commands
            if isinstance(command, SetSlotCommand) and command.value
        ]
        structlogger.debug(
            "multi_step_llm_command_generator"
            ".predict_commands_for_newly_started_flow"
            ".filtered_commands",
            flow=flow.id,
            commands=commands,
        )

        return commands

    def prepare_inputs(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
        max_turns: int = 1,
    ) -> Dict[str, Any]:
        top_relevant_frame = top_flow_frame(tracker.stack)
        top_flow = top_relevant_frame.flow(flows) if top_relevant_frame else None
        current_step = top_relevant_frame.step(flows) if top_relevant_frame else None
        if top_flow is not None:
            flow_slots = self.prepare_current_flow_slots_for_template(
                top_flow, current_step, tracker
            )
            top_flow_is_pattern = top_flow.is_rasa_default_flow
        else:
            flow_slots = []
            top_flow_is_pattern = False

        if top_flow_is_pattern:
            top_user_frame = top_user_flow_frame(tracker.stack)
            top_user_flow = top_user_frame.flow(flows) if top_user_frame else None
            top_user_flow_step = top_user_frame.step(flows) if top_user_frame else None
            top_user_flow_slots = self.prepare_current_flow_slots_for_template(
                top_user_flow, top_user_flow_step, tracker
            )
        else:
            top_user_flow = None
            top_user_flow_slots = []

        current_slot, current_slot_description = self.prepare_current_slot_for_template(
            current_step
        )
        current_slot_type = None
        current_slot_allowed_values = None
        if current_slot:
            current_slot_type = (
                slot.type_name
                if (slot := tracker.slots.get(current_slot)) is not None
                else None
            )
            current_slot_allowed_values = self.allowed_values_for_slot(
                tracker.slots.get(current_slot)
            )
        (
            current_conversation,
            latest_user_message,
        ) = self.prepare_conversation_context_for_template(message, tracker, max_turns)

        inputs = {
            "available_flows": self.prepare_flows_for_template(flows, tracker),
            "current_conversation": current_conversation,
            "current_flow": top_flow.id if top_flow is not None else None,
            "current_slot": current_slot,
            "current_slot_description": current_slot_description,
            "current_slot_type": current_slot_type,
            "current_slot_allowed_values": current_slot_allowed_values,
            "last_user_message": latest_user_message,
            "flow_slots": flow_slots,
            "top_flow_is_pattern": top_flow_is_pattern,
            "top_user_flow": top_user_flow.id if top_user_flow is not None else None,
            "top_user_flow_slots": top_user_flow_slots,
            "flow_active": True,
        }
        return inputs

    def prepare_inputs_for_single_flow(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flow: Flow,
        max_turns: int = 1,
    ) -> Dict[Text, Any]:
        flow_slots = self.prepare_current_flow_slots_for_template(
            flow, flow.first_step_in_flow(), tracker
        )
        (
            current_conversation,
            latest_user_message,
        ) = self.prepare_conversation_context_for_template(message, tracker, max_turns)
        inputs = {
            "current_conversation": current_conversation,
            "flow_slots": flow_slots,
            "current_flow": flow.id,
            "last_user_message": latest_user_message,
            "flow_active": False,
        }
        return inputs

    async def _invoke_llm(self, prompt: Text) -> Optional[Text]:
        """Use LLM to generate a response.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            The generated text.
        """
        llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)
        try:
            return await llm.apredict(prompt)
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("multi_step_llm_command_generator.llm.error", error=e)
            return None

    @classmethod
    def parse_commands(
        cls,
        actions: Optional[str],
        tracker: DialogueStateTracker,
        flows: FlowsList,
        is_start_or_end_prompt: bool = False,
    ) -> List[Command]:
        """Parse the actions returned by the llm into intent and entities.

        Args:
            actions: The actions returned by the llm.
            tracker: The tracker containing the current state of the conversation.
            flows: The list of flows.
            is_start_or_end_prompt: bool

        Returns:
            The parsed commands.
        """
        if not actions:
            return [ErrorCommand()]

        commands: List[Command] = []

        slot_set_re = re.compile(
            r"""SetSlot\((\"?[a-zA-Z_][a-zA-Z0-9_-]*?\"?), ?(.*)\)"""
        )
        start_flow_re = re.compile(r"StartFlow\(([a-zA-Z0-9_-]+?)\)")
        change_flow_re = re.compile(r"ChangeFlow\(\)")
        cancel_flow_re = re.compile(r"CancelFlow\(\)")
        cannot_handle_re = re.compile(r"CannotHandle\(\)")

        clarify_re = re.compile(r"Clarify\(([\"\'a-zA-Z0-9_, ]+)\)")

        for action in actions.strip().splitlines():
            if is_start_or_end_prompt:
                if (
                    len(commands) >= 2
                    or len(commands) == 1
                    and isinstance(commands[0], ClarifyCommand)
                ):
                    break
            if cannot_handle_re.search(action):
                commands = [CannotHandleCommand()]
                break
            elif match := slot_set_re.search(action):
                slot_name = cls.clean_extracted_value(match.group(1).strip())
                slot_value = cls.clean_extracted_value(match.group(2))
                # error case where the llm tries to start a flow using a slot set
                if slot_name == "flow_name":
                    commands.extend(cls.start_flow_by_name(slot_value, flows))
                else:
                    typed_slot_value = cls.get_nullable_slot_value(slot_value)
                    commands.append(
                        SetSlotCommand(name=slot_name, value=typed_slot_value)
                    )
            elif match := start_flow_re.search(action):
                flow_name = match.group(1).strip()
                commands.extend(cls.start_flow_by_name(flow_name, flows))
            elif cancel_flow_re.search(action):
                commands.append(CancelFlowCommand())
            elif match := clarify_re.search(action):
                options = sorted([opt.strip() for opt in match.group(1).split(",")])
                valid_options = [
                    flow
                    for flow in options
                    if flow in flows.user_flow_ids
                    and flow not in user_flows_on_the_stack(tracker.stack)
                ]
                if len(valid_options) == 1:
                    commands.extend(cls.start_flow_by_name(valid_options[0], flows))
                elif 1 < len(valid_options) <= 5:
                    commands.append(ClarifyCommand(valid_options))
            elif change_flow_re.search(action):
                commands.append(ChangeFlowCommand())

        return commands

    @staticmethod
    def start_flow_by_name(flow_name: str, flows: FlowsList) -> List[Command]:
        """Start a flow by name.

        If the flow does not exist, no command is returned."""
        if flow_name in flows.user_flow_ids:
            return [StartFlowCommand(flow=flow_name)]
        else:
            structlogger.debug(
                "multi_step_llm_command_generator.flow.start_invalid_flow_id",
                flow=flow_name,
            )
            return []

    @staticmethod
    def is_none_value(value: Text) -> bool:
        """Check if the value is a none value."""
        return value.lower() in {
            "[missing information]",
            "[missing]",
            "none",
            "null",
            "undefined",
            "unknown",
            "",
            "?",
            "not provided",
        }

    @staticmethod
    def clean_extracted_value(value: Text) -> Text:
        """Clean up the extracted value from the llm."""
        # replace any combination of single quotes, double quotes, and spaces
        # from the beginning and end of the string
        return value.strip("'\" ")

    @classmethod
    def get_nullable_slot_value(cls, slot_value: Text) -> Optional[Text]:
        """Get the slot value or None if the value is a none value.

        Args:
            slot_value: the value to coerce

        Returns:
            The slot value or None if the value is a none value.
        """
        return (
            slot_value
            if slot_value is not None and not cls.is_none_value(slot_value)
            else None
        )

    def prepare_flows_for_template(
        self, flows: FlowsList, tracker: DialogueStateTracker
    ) -> List[Dict[Text, Any]]:
        """Format data on available flows for insertion into the prompt template.

        Args:
            flows: The flows available to the user.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The inputs for the prompt template.
        """
        result = []
        for flow in flows.user_flows:
            slots_with_info = [
                {
                    "name": q.collect,
                    "description": q.description,
                    "allowed_values": self.allowed_values_for_slot(
                        tracker.slots[q.collect]
                    ),
                }
                for q in flow.get_collect_steps()
                if self.is_extractable(q, tracker)
            ]
            result.append(
                {
                    "name": flow.id,
                    "description": flow.description,
                    "slots": slots_with_info,
                }
            )
        return result

    @staticmethod
    def prepare_conversation_context_for_template(
        message: Message, tracker: DialogueStateTracker, max_turns: int = 20
    ) -> Tuple[Text, Text]:
        current_conversation = tracker_as_readable_transcript(
            tracker, max_turns=max_turns
        )
        latest_user_message = sanitize_message_for_prompt(message.get(TEXT))
        current_conversation += f"\nUSER: {latest_user_message}"
        return current_conversation, latest_user_message

    def prepare_current_flow_slots_for_template(
        self, top_flow: Flow, current_step: FlowStep, tracker: DialogueStateTracker
    ) -> List[Dict[Text, Any]]:
        """Prepare the current flow slots for the template.

        Args:
            top_flow: The top flow.
            current_step: The current step in the flow.
            tracker: The tracker containing the current state of the conversation.

        Returns:
            The slots with values, types, allowed values and a description.
        """
        if top_flow is not None:
            flow_slots = [
                {
                    "name": collect_step.collect,
                    "value": self.get_slot_value(tracker, collect_step.collect),
                    "type": tracker.slots[collect_step.collect].type_name,
                    "allowed_values": self.allowed_values_for_slot(
                        tracker.slots[collect_step.collect]
                    ),
                    "description": collect_step.description,
                }
                for collect_step in top_flow.get_collect_steps()
                if self.is_extractable(collect_step, tracker, current_step)
            ]
        else:
            flow_slots = []
        return flow_slots

    @staticmethod
    def prepare_current_slot_for_template(
        current_step: FlowStep,
    ) -> Tuple[Union[str, None], Union[str, None]]:
        """Prepare the current slot for the template."""
        return (
            (current_step.collect, current_step.description)
            if isinstance(current_step, CollectInformationFlowStep)
            else (None, None)
        )

    @staticmethod
    def is_extractable(
        collect_step: CollectInformationFlowStep,
        tracker: DialogueStateTracker,
        current_step: Optional[FlowStep] = None,
    ) -> bool:
        """Check if the `collect` can be filled.

        A collect slot can only be filled if the slot exist
        and either the collect has been asked already or the
        slot has been filled already.

        Args:
            collect_step: The collect_information step.
            tracker: The tracker containing the current state of the conversation.
            current_step: The current step in the flow.

        Returns:
            `True` if the slot can be filled, `False` otherwise.
        """
        slot = tracker.slots.get(collect_step.collect)
        if slot is None:
            return False

        return (
            # we can fill because this is a slot that can be filled ahead of time
            not collect_step.ask_before_filling
            # we can fill because the slot has been filled already
            or slot.has_been_set
            # we can fill because the is currently getting asked
            or (
                current_step is not None
                and isinstance(current_step, CollectInformationFlowStep)
                and current_step.collect == collect_step.collect
            )
        )

    @staticmethod
    def allowed_values_for_slot(slot: Slot) -> Union[str, None]:
        """Get the allowed values for a slot."""
        if isinstance(slot, BooleanSlot):
            return str([True, False])
        if isinstance(slot, CategoricalSlot):
            return str([v for v in slot.values if v != "__other__"])
        else:
            return None

    @staticmethod
    def get_slot_value(tracker: DialogueStateTracker, slot_name: str) -> str:
        """Get the slot value from the tracker.

        Args:
            tracker: The tracker containing the current state of the conversation.
            slot_name: The name of the slot.

        Returns:
            The slot value as a string.
        """
        slot_value = tracker.get_slot(slot_name)
        if slot_value is None:
            return "undefined"
        else:
            return str(slot_value)

    @classmethod
    def fingerprint_addon(cls, config: Dict[str, Any]) -> Optional[str]:
        """Add a fingerprint for the graph."""
        start_or_end_flows_template = get_prompt_template(
            config.get("prompts", {}).get(START_OR_END_FLOW_KEY, {}).get(FILE_PATH_KEY),
            DEFAULT_START_OR_END_FLOWS_TEMPLATE,
        )
        fill_slots_template = get_prompt_template(
            config.get("prompts", {}).get(FILL_SLOTS_KEY, {}).get(FILE_PATH_KEY),
            DEFAULT_FILL_SLOTS_TEMPLATE,
        )
        return deep_container_fingerprint(
            [
                start_or_end_flows_template,
                fill_slots_template,
            ]
        )

