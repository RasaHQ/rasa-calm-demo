from inspect_ai import Task, eval, task
from inspect_ai.dataset import example_dataset
from inspect_ai.scorer import model_graded_fact
from inspect_ai.solver import (               
  chain_of_thought, generate, self_critique   
)                                             

@task
def theory_of_mind():
    # The Task object brings together the dataset, solvers, and scorer, 
    # And is then evaluated using a model.
    return Task(
        dataset=example_dataset("theory_of_mind"),
        plan=[
           # In this example we are chaining together three standard solver components. 
          # It’s also possible to create a more complex custom solver that manages state 
          # And interactions internally.
          chain_of_thought(),
          generate(),
          self_critique()
        ],
        scorer=model_graded_fact()
    )