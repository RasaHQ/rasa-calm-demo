from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, json_dataset
from inspect_ai.solver import generate, solver, TaskState, Generate
from inspect_ai.util import resource
from inspect_ai.scorer import scorer, Score, CORRECT, INCORRECT, Target

@solver
def prompt_with_actions():
    """Create LLM Judge prompt with the conversation and actions"""
    template = resource("llm-judge-prompt-template.txt")
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Extract required fields from metadata
        conversation = state.input_text
        actions = state.metadata.get('actions', '')
        flow_desc = state.metadata.get('flow_desc', '')
        cmd_desc = state.metadata.get('cmd_desc', '')
        search_response = state.metadata.get('search_response', '')

        # Format the template with all required fields
        formatted_prompt = template.format(
            conversation=conversation,
            action_list=actions,
            flow_description=flow_desc,
            command_description=cmd_desc,
            search_response=search_response
        )

        # Replace the user prompt with our formatted prompt
        state.user_prompt.text = formatted_prompt
        return state

    return solve

@scorer(metrics=["accuracy", "stderr"])
def match_target():
    """Check if the model output matches the target answer"""
    async def score(state: TaskState, target: Target) -> Score:
        model_output = state.output.completion.strip()
        correct_answer = target.text.strip()
        
        is_correct = model_output == correct_answer
        
        return Score(
            value=CORRECT if is_correct else INCORRECT,
            answer=model_output,
            explanation=f"Model output: '{model_output}', Correct answer: '{correct_answer}'"
        )
    
    return score

@task
def llm_judge():
    """Inspect AI task for LLM Judge"""
    dataset = json_dataset(
        "conversations.jsonl",
        FieldSpec(
            input="conversation",
            target="target",
            id="id",
            metadata=["actions", "flow_desc", "cmd_desc", "search_response"],
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