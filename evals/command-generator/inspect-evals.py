from inspect_ai import Task
from inspect_ai.dataset import csv_dataset, FieldSpec

def command_generator():
    return Task(
        dataset=csv_dataset(
            'evals/commands.csv', 
            FieldSpec(input="Question", target="Commands")
        ),
        plan=[
            prompt_template()
        ]
    )