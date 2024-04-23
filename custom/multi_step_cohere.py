import importlib.resources
import re
from typing import Dict, Any, List, Optional, Tuple, Union
import cohere
import structlog
from jinja2 import Template

from rasa.dialogue_understanding.commands import (
    Command,
    ErrorCommand,
    SetSlotCommand,
    CancelFlowCommand,
    StartFlowCommand,
    HumanHandoffCommand,
    ChitChatAnswerCommand,
    SkipQuestionCommand,
    KnowledgeAnswerCommand,
    ClarifyCommand,
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
from langchain.callbacks import OpenAICallbackHandler

openai_callback_handler = OpenAICallbackHandler()
times = []

REFINE_SLOT_PROMPT_FILE_NAME = "refine_slot_prompt.jinja2"
SUMMARIZE_CONVERSATION_PROMPT_FILE_NAME = "summarize_conversation_prompt.jinja2"
START_OR_END_FLOWS_PROMPT_FILE_NAME = "start_or_end_flows_prompt.jinja2"
FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_PROMPT_FILE_NAME = (
    "fill_slots_for_newly_started_flow_prompt.jinja2"
)
FILL_SLOTS_OF_CURRENT_FLOW_PROMPT_FILE_NAME = "fill_slots_of_current_flow_prompt.jinja2"

REFINE_SLOT_TEMPLATE_KEY = "refine_slot_template"
SUMMARIZE_CONVERSATION_TEMPLATE_KEY = "summarize_conversation_template"
START_OR_END_FLOWS_TEMPLATE_KEY = "start_or_end_flows_template"
FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE_KEY = (
    "fill_slots_for_newly_started_flow_template"
)
FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE_KEY = "fill_slots_of_current_flow_template"

DEFAULT_REFINE_SLOT_TEMPLATE = importlib.resources.read_text(
    "custom", "refine_slot.jinja2"
).strip()

DEFAULT_SUMMARIZE_CONVERSATION_TEMPLATE = importlib.resources.read_text(
    "custom", "summarize_conversation.jinja2"
).strip()

DEFAULT_START_OR_END_FLOWS_TEMPLATE = importlib.resources.read_text(
    "custom", "start_or_end_flows.jinja2"
).strip()

DEFAULT_FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE = importlib.resources.read_text(
    "custom", "fill_slots_for_newly_started_flow.jinja2"
).strip()

DEFAULT_FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE = importlib.resources.read_text(
    "custom", "fill_slots_of_current_flow.jinja2"
).strip()

DEFAULT_LLM_CONFIG = {
    "_type": "openai",
    "request_timeout": 7,
    "temperature": 0.0,
    "model_name": DEFAULT_OPENAI_CHAT_MODEL_NAME_ADVANCED,
    "max_tokens": DEFAULT_OPENAI_MAX_GENERATED_TOKENS,
}

LLM_CONFIG_KEY = "llm"
USER_INPUT_CONFIG_KEY = "user_input"

structlogger = structlog.get_logger()


@DefaultV1Recipe.register(
    [
        DefaultV1Recipe.ComponentType.COMMAND_GENERATOR,
    ],
    is_trainable=True,
)
class MultiStepLLMCommandGenerator(GraphComponent, CommandGenerator):
    """An LLM-based multi step command generator."""

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
        config: Dict[str, Any],
        model_storage: ModelStorage,
        resource: Resource,
        prompt_templates: Optional[Dict[str, Optional[str]]] = None,
    ) -> None:
        super().__init__(config)
        self.config = {**self.get_default_config(), **config}
        self.refine_slot_prompt = self.load_prompt_template(
            prompt_templates,
            config,
            REFINE_SLOT_TEMPLATE_KEY,
            DEFAULT_REFINE_SLOT_TEMPLATE,
        )
        self.summarize_conversation_prompt = self.load_prompt_template(
            prompt_templates,
            config,
            SUMMARIZE_CONVERSATION_TEMPLATE_KEY,
            DEFAULT_SUMMARIZE_CONVERSATION_TEMPLATE,
        )
        self.start_or_end_flows_prompt = self.load_prompt_template(
            prompt_templates,
            config,
            START_OR_END_FLOWS_TEMPLATE_KEY,
            DEFAULT_START_OR_END_FLOWS_TEMPLATE,
        )
        self.fill_slots_for_newly_started_flow_prompt = self.load_prompt_template(
            prompt_templates,
            config,
            FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE_KEY,
            DEFAULT_FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE,
        )
        self.fill_slots_of_current_flow_prompt = self.load_prompt_template(
            prompt_templates,
            config,
            FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE_KEY,
            DEFAULT_FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE,
        )

        self._model_storage = model_storage
        self._resource = resource

    @staticmethod
    def load_prompt_template(
        prompt_templates: Optional[Dict[str, Optional[str]]],
        config: Dict[str, Any],
        key: str,
        default_value: str,
    ) -> str:
        if prompt_templates and key in prompt_templates:
            return prompt_templates[key]
        return get_prompt_template(
            config["prompts"].get(key),
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
        prompts = {}
        try:
            with model_storage.read_from(resource) as path:
                prompts[REFINE_SLOT_TEMPLATE_KEY] = rasa.shared.utils.io.read_file(
                    path / REFINE_SLOT_PROMPT_FILE_NAME
                )
                prompts[
                    SUMMARIZE_CONVERSATION_TEMPLATE_KEY
                ] = rasa.shared.utils.io.read_file(
                    path / SUMMARIZE_CONVERSATION_PROMPT_FILE_NAME
                )
                prompts[
                    SUMMARIZE_CONVERSATION_TEMPLATE_KEY
                ] = rasa.shared.utils.io.read_file(
                    path / START_OR_END_FLOWS_PROMPT_FILE_NAME
                )
                prompts[
                    FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE_KEY
                ] = rasa.shared.utils.io.read_file(
                    path / FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_PROMPT_FILE_NAME
                )
                prompts[
                    FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE_KEY
                ] = rasa.shared.utils.io.read_file(
                    path / FILL_SLOTS_OF_CURRENT_FLOW_PROMPT_FILE_NAME
                )

        except (FileNotFoundError, FileIOException) as e:
            structlogger.warning(
                "llm_command_generator.load.failed", error=e, resource=resource.name
            )

        return cls(config, model_storage, resource, prompts)

    def persist(self) -> None:
        """Persist this component to disk for future loading."""
        with self._model_storage.write_to(self._resource) as path:
            rasa.shared.utils.io.write_text_file(
                self.refine_slot_prompt, path / REFINE_SLOT_PROMPT_FILE_NAME
            )
            rasa.shared.utils.io.write_text_file(
                self.summarize_conversation_prompt,
                path / SUMMARIZE_CONVERSATION_PROMPT_FILE_NAME,
            )
            rasa.shared.utils.io.write_text_file(
                self.start_or_end_flows_prompt,
                path / START_OR_END_FLOWS_PROMPT_FILE_NAME,
            )
            rasa.shared.utils.io.write_text_file(
                self.fill_slots_of_current_flow_prompt,
                path / FILL_SLOTS_OF_CURRENT_FLOW_PROMPT_FILE_NAME,
            )
            rasa.shared.utils.io.write_text_file(
                self.fill_slots_for_newly_started_flow_prompt,
                path / FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_PROMPT_FILE_NAME,
            )

    def train(self, training_data: TrainingData) -> Resource:
        """Train the intent classifier on a data set."""
        self.persist()
        return self._resource

    def predict_commands(
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

        (
            commands_from_active_flow,
            should_change_flows,
        ) = self.predict_commands_for_active_flow(message, tracker, flows)

        if should_change_flows:
            commands_for_starting_or_ending_flows = (
                self.predict_commands_for_starting_and_ending_flows(
                    message,
                    tracker,
                    flows,
                )
            )
        else:
            commands_for_starting_or_ending_flows = []

        start_flow_commands = [
            c
            for c in commands_for_starting_or_ending_flows
            if isinstance(c, StartFlowCommand)
        ]

        commands_for_newly_started_flows = []
        for start_flow_command in start_flow_commands:
            commands_for_newly_started_flows += (
                self.predict_commands_for_newly_started_flow(
                    start_flow_command, message, tracker, flows
                )
            )

        commands = (
            commands_from_active_flow
            + commands_for_starting_or_ending_flows
            + commands_for_newly_started_flows
        )

        slot_commands = [c for c in commands if isinstance(c, SetSlotCommand)]
        commands_without_slots = [
            c for c in commands if not isinstance(c, SetSlotCommand)
        ]
        new_flows = [c.flow for c in commands if isinstance(c, StartFlowCommand)]
        refined_slot_commands = self.refine_slot_commands(
            slot_commands, new_flows, tracker, flows
        )

        commands = commands_without_slots + refined_slot_commands

        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands.finished",
            commands=commands,
        )

        return commands

    def refine_slot_commands(
        self,
        slot_commands: List[SetSlotCommand],
        new_flows: List[str],
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> [Command]:
        top_frame = top_flow_frame(tracker.stack)

        active_and_new_flows = user_flows_on_the_stack(tracker.stack) | set(new_flows)
        if top_frame:
            active_and_new_flows.add(top_frame.flow_id)
        slots_of_active_flows = {}
        for flow_id in active_and_new_flows:
            flow = flows.flow_by_id(flow_id)
            if flow is None:
                continue
            for q in flow.get_collect_steps():
                allowed_values = self.allowed_values_for_slot(tracker.slots[q.collect])
                slots_of_active_flows[q.collect] = {
                    "description": q.description if q.description else None,
                    "allowed_values": allowed_values,
                }
        structlogger.debug(
            "multi_step_llm_command_generator.refine_slots.info_collected",
            slots=slots_of_active_flows,
        )
        refined_commands = []
        for c in slot_commands:

            info = slots_of_active_flows.get(c.name)
            print(c.name,c.value, info)
            if info is None:
                continue
            if c.value is None:
                refined_commands.append(c)
                continue
            if info["allowed_values"] and c.value in info["allowed_values"].strip(
                "[] "
            ).split(", "):
                refined_commands.append(c)
                continue
            inputs = {
                "slot": c.name,
                "potential_value": c.value,
                "slot_description": info["description"],
                "allowed_values": info["allowed_values"],
            }
            print(inputs)
            prompt = Template(self.refine_slot_prompt).render(**inputs)
            structlogger.debug(
                "multi_step_llm_command_generator.refine_slots.prompt_rendered",
                prompt=prompt,
            )
            # llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)

            try:
                new_value = self.invoke_llm(prompt)
                new_value = self.clean_extracted_value(new_value)
                if c.name in new_value:
                    structlogger.debug(
                        "multi_step_llm_command_generator.refine_slots.drop_new_value",
                        new_value=new_value,
                    )
                    new_value = c.value
                structlogger.debug(
                    "multi_step_llm_command_generator.refine_slots.new_value",
                    new_value=new_value,
                )
                refined_commands.append(SetSlotCommand(c.name, new_value))
            except Exception as e:
                # unfortunately, langchain does not wrap LLM exceptions which means
                # we have to catch all exceptions here
                structlogger.error(
                    "multi_step_llm_command_generator.llm.error", error=e
                )
                refined_commands.append(c)
        print(refined_commands)
        return refined_commands

    def predict_commands_for_newly_started_flow(
        self,
        start_flow_command: StartFlowCommand,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> [Command]:

        flow = flows.flow_by_id(start_flow_command.flow)
        flow_slots = self.prepare_current_flow_slots_for_template(
            flow, flow.first_step_in_flow(), tracker
        )
        if len(flow_slots) == 0:
            # return empty if the newly started flow does not have any slots
            return []
        current_conversation = tracker_as_readable_transcript(tracker)
        latest_user_message = sanitize_message_for_prompt(message.get(TEXT))
        current_conversation += f"\nUSER: {latest_user_message}"

        inputs = {
            "current_conversation": current_conversation,
            "flow_slots": flow_slots,
            "current_flow": flow.id,
            "last_user_message": latest_user_message,
        }

        prompt = Template(self.fill_slots_for_newly_started_flow_prompt).render(
            **inputs
        )
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_newly_started_flow."
            "prompt_rendered",
            prompt=prompt,
        )

        # llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)

        try:
            actions = self.invoke_llm(prompt)
            # actions = llm(prompt, callbacks=[openai_callback_handler])
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("multi_step_llm_command_generator.llm.error", error=e)
            return []
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_newly_started_flow."
            "actions_generated",
            action_list=actions,
        )
        commands = self.parse_commands(actions, tracker, flows)
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_newly_started_flow."
            "commands",
            commands=commands,
        )
        # filter out all commands that unset values for newly started flow
        filtered_commands = [c for c in commands if isinstance(c, SetSlotCommand) and c.value]
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_newly_started_flow."
            "filtered_commands",
            filtered_commands=commands,
        )
        return filtered_commands

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
            top_user_flow_step = top_user_frame.step(flows) if top_user_flow else None
            top_user_flow_slots = self.prepare_current_flow_slots_for_template(
                top_user_flow, top_user_flow_step, tracker
            )
        else:
            top_user_flow = None
            top_user_flow_slots = []

        current_slot, current_slot_description = self.prepare_current_slot_for_template(
            current_step
        )
        current_conversation = tracker_as_readable_transcript(
            tracker, max_turns=max_turns
        )
        latest_user_message = sanitize_message_for_prompt(message.get(TEXT))
        current_conversation += f"\nUSER: {latest_user_message}"

        inputs = {
            "available_flows": self.prepare_flows_for_template(flows, tracker),
            "current_conversation": current_conversation,
            "current_flow": top_flow.id if top_flow is not None else None,
            "current_slot": current_slot,
            "current_slot_description": current_slot_description,
            "last_user_message": latest_user_message,
            "flow_slots": flow_slots,
            "top_flow_is_pattern": top_flow_is_pattern,
            "top_user_flow": top_user_flow.id if top_user_flow is not None else None,
            "top_user_flow_slots": top_user_flow_slots,
        }
        return inputs

    def predict_commands_for_starting_and_ending_flows(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> [Command]:
        inputs = self.prepare_inputs(message, tracker, flows, 2)
        prompt = Template(self.start_or_end_flows_prompt).render(**inputs).strip()
        # llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)
        structlogger.debug(
            "multi_step_llm_command_generator."
            "predict_commands_for_starting_and_ending_flows.prompt_rendered",
            prompt=prompt,
        )

        try:
            # actions = llm(prompt, callbacks=[openai_callback_handler])
            actions = self.invoke_llm(prompt)
            structlogger.debug(
                "multi_step_llm_command_generator."
                "predict_commands_for_starting_and_ending_flows.actions_generated",
                action_list=actions,
            )
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("multi_step_llm_command_generator.llm.error", error=e)
            return []
        commands = self.parse_commands(actions, tracker, flows, True)

        frames = tracker.stack.frames
        active_user_flows = {
            f.flow_id for f in frames if isinstance(f, UserFlowStackFrame)
        }

        commands = [
            c
            for c in commands
            if not (isinstance(c, StartFlowCommand) and c.flow in active_user_flows)
        ]

        return commands

    def invoke_llm(self, prompt):
        co = cohere.Client('*')
        try:
            # print("sending check")
            # print(llm)
            response = co.chat(
              model="command-r",
              chat_history=[],
              message=prompt,
              # temperature=0.0
            )
            # print(response)
            #
            # output = response.content[0].text
            # print(output)
            return response.text
            # return llm(prompt, stop=["<|im_end|>","<|im_start|>"])
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("llm_command_generator.llm.error", error=e)
            return None

    def predict_commands_for_active_flow(
        self,
        message: Message,
        tracker: DialogueStateTracker,
        flows: FlowsList,
    ) -> Tuple[List[Command], bool]:
        inputs = self.prepare_inputs(message, tracker, flows)
        if inputs["current_flow"] is None:
            return [], True
        prompt = (
            Template(self.fill_slots_of_current_flow_prompt).render(**inputs).strip()
        )
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_active_flow."
            "prompt_rendered",
            prompt=prompt,
        )

        # llm = llm_factory(self.config.get(LLM_CONFIG_KEY), DEFAULT_LLM_CONFIG)

        try:
            actions = self.invoke_llm(prompt)
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error("multi_step_llm_command_generator.llm.error", error=e)
            return [], True
        structlogger.debug(
            "multi_step_llm_command_generator.predict_commands_for_active_flow."
            "actions_generated",
            action_list=actions,
        )
        commands = self.parse_commands(actions, tracker, flows)

        # check whether the change flow command was among the generated commands
        filtered_commands = [
            c
            for c in commands
            if not (isinstance(c, StartFlowCommand) and c.flow == "XXXX")
        ]
        return filtered_commands, len(commands) != len(filtered_commands)

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

        slot_set_re = re.compile(r"""SetSlot\((\"?[a-zA-Z_][a-zA-Z0-9_-]*?\"?), ?(.*)\)""")
        start_flow_re = re.compile(r"StartFlow\(([a-zA-Z0-9_-]+?)\)")
        change_flow_re = re.compile(r"ChangeFlow\(\)")
        cancel_flow_re = re.compile(r"CancelFlow\(\)")
        chitchat_re = re.compile(r"ChitChat\(\)")
        skip_question_re = re.compile(r"SkipQuestion\(\)")
        knowledge_re = re.compile(r"SearchAndReply\(\)")
        humand_handoff_re = re.compile(r"HumanHandoff\(\)")
        clarify_re = re.compile(r"Clarify\(([a-zA-Z0-9_, ]+)\)")

        for action in actions.strip().splitlines():
            if is_start_or_end_prompt:
                if (
                    len(commands) >= 2
                    or len(commands) == 1
                    and isinstance(commands[0], ClarifyCommand)
                ):
                    break

            if match := slot_set_re.search(action):
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
            elif chitchat_re.search(action):
                commands.append(ChitChatAnswerCommand())
            elif skip_question_re.search(action):
                commands.append(SkipQuestionCommand())
            elif knowledge_re.search(action):
                commands.append(KnowledgeAnswerCommand())
            elif humand_handoff_re.search(action):
                commands.append(HumanHandoffCommand())
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
                commands.append(StartFlowCommand("XXXX"))

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
    def is_none_value(value: str) -> bool:
        """Check if the value is a none value."""
        return value in {
            "[missing information]",
            "[missing]",
            "None",
            "undefined",
            "null",
            "",
        }

    @staticmethod
    def clean_extracted_value(value: str) -> str:
        """Clean up the extracted value from the llm."""
        # replace any combination of single quotes, double quotes, and spaces
        # from the beginning and end of the string
        return value.strip("'\" ")

    @classmethod
    def get_nullable_slot_value(cls, slot_value: str) -> Union[str, None]:
        """Get the slot value or None if the value is a none value.

        Args:
            slot_value: the value to coerce

        Returns:
            The slot value or None if the value is a none value.
        """
        return slot_value if not cls.is_none_value(slot_value) else None

    def prepare_flows_for_template(
        self, flows: FlowsList, tracker: DialogueStateTracker
    ) -> List[Dict[str, Any]]:
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

    def prepare_current_flow_slots_for_template(
        self, top_flow: Flow, current_step: FlowStep, tracker: DialogueStateTracker
    ) -> List[Dict[str, Any]]:
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
            current_step: FlowStep
    ) -> Tuple[Union[str, None], Union[str, None]]:
        """Prepare the current slot for the template."""
        return (
            (current_step.collect, current_step.description)
            if isinstance(current_step, CollectInformationFlowStep)
            else (None, None)
        )

    @classmethod
    def fingerprint_addon(cls, config: Dict[str, Any]) -> Optional[str]:
        """Add a fingerprint for the graph."""
        refine_slot_template = get_prompt_template(
            config["prompts"].get(REFINE_SLOT_TEMPLATE_KEY),
            DEFAULT_REFINE_SLOT_TEMPLATE,
        )
        summarize_conversation_template = get_prompt_template(
            config["prompts"].get(SUMMARIZE_CONVERSATION_TEMPLATE_KEY),
            DEFAULT_SUMMARIZE_CONVERSATION_TEMPLATE,
        )
        start_or_end_flows_template = get_prompt_template(
            config["prompts"].get(START_OR_END_FLOWS_TEMPLATE_KEY),
            DEFAULT_START_OR_END_FLOWS_TEMPLATE,
        )
        fill_slots_for_newly_started_flow_template = get_prompt_template(
            config["prompts"].get(FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE_KEY),
            DEFAULT_FILL_SLOTS_FOR_NEWLY_STARTED_FLOW_TEMPLATE,
        )
        fill_slots_of_current_flow_template = get_prompt_template(
            config["prompts"].get(FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE_KEY),
            DEFAULT_FILL_SLOTS_OF_CURRENT_FLOW_TEMPLATE,
        )
        return deep_container_fingerprint(
            [
                refine_slot_template,
                summarize_conversation_template,
                start_or_end_flows_template,
                fill_slots_for_newly_started_flow_template,
                fill_slots_of_current_flow_template,
            ]
        )
