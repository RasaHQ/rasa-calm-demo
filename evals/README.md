Refers to evaluation discussed here, https://www.notion.so/rasa/Evaluation-Plan-for-Enterprise-Search-Triggering-Improvements-9d03f24f728343a4931bdc122d1be862?d=8a76cc258b294f3c9af0a95e1565d69f#c52a5e11959045da8663481eab9aa2ab

# Recreating the LLM Judge Evaluation

1. Create a new virtual environment in the `evals` directory. It is important that you aren't using the same virtual environment as rasa-calm-demo as openai versions required by rasa-calm-demo is incompatible with inspect_ai. Rasa uses a very old openai package

2. Install the dependencies `inspect_ai` and `openai` packages. Azure Models do not require any additional packages but if you intend to use any other providers ([see this page](https://inspect.ai-safety-institute.org.uk/models.html))

3. Make sure that the OPENAI API Key environment variable is set

4. Run Inspect evaluation with the following command

```
inspect eval llm-judge/eval.py@llm_judge --model openai/gpt-4o-mini
```

# Evaluation Results Viewer

Start the Inspect View,
```
inspect view
```

# Importing or Exporting Logs

If you have already run any evaluations with Inspect, you will have a `logs` directory at the base of project.

If you do not have the `logs` directory, create it and add the JSON logs you would like to view.

You can copy the existing JSON logs or add new JSON logs in this directory. These logs will be available in the Inspect View