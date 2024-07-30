from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, csv_dataset
from inspect_ai.solver import generate, solver, TaskState, Generate
from inspect_ai.util import resource
from inspect_ai.scorer import scorer, Score, CORRECT, INCORRECT, Target, accuracy

ID_KEY = "ID"
CONVERSATION_KEY = "Conversation"
ACTIONS_KEY = "Action List"
FLOWS_KEY = "Flow Description"
CMD_KEY = "Command Description"
SEARCH_KEY = "Search Response"
HUMAN_ANNOTATED_RESPONSE = "Target"

@solver
def prompt_with_actions():
    """Create LLM Judge prompt with the conversation and actions"""
    template = resource("llm-judge-prompt-template.txt")
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Extract required fields from metadata
        conversation = state.input_text
        actions = state.metadata.get(ACTIONS_KEY, '')
        cmd_desc = state.metadata.get(CMD_KEY, '')
        search_response = state.metadata.get(SEARCH_KEY, '')

        flow_desc = state.metadata.get(FLOWS_KEY, '')
        if flow_desc:
            flow = f"Flow Description: {flow_desc}"
        else:
            flow = ""

        # Format the template with all required fields
        formatted_prompt = template.format(
            conversation=conversation,
            action_list=actions,
            flow_description=flow,
            command_description=cmd_desc,
            search_response=search_response
        )

        # Replace the user prompt with our formatted prompt
        state.user_prompt.text = formatted_prompt
        return state

    return solve

@scorer(metrics=[accuracy()])
def match_target():
    """Check if the model output matches the target answer"""
    async def score(state: TaskState, target: Target) -> Score:
        model_output = state.output.completion.strip()
        correct_answer = target.text.strip()

        # extract the first line of the model output
        model_choice = model_output.split("\n")[0].strip()
        
        is_correct = model_choice == correct_answer
        
        return Score(
            value=CORRECT if is_correct else INCORRECT,
            answer=model_output,
            explanation=f"Model output: '{model_output}', Correct answer: '{correct_answer}'"
        )
    
    return score

@task
def llm_judge():
    """Inspect AI task for LLM Judge"""
    dataset = csv_dataset(
        "conversations.csv",
        FieldSpec(
            input=CONVERSATION_KEY,
            target=HUMAN_ANNOTATED_RESPONSE,
            id=ID_KEY,
            metadata=[ACTIONS_KEY, FLOWS_KEY, CMD_KEY, SEARCH_KEY],
        ),
    )

    return Task(
        dataset=dataset,
        plan=[
            prompt_with_actions(),
            generate()
        ],
        scorer=match_target(),
    )