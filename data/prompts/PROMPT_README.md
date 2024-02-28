# Prompts README

This README provides information on how to use the prompts and includes the results of the end-to-end (e2e) tests for different models.

## Usage

```
name: LLMCommandGenerator
prompt: path_to_prompt_file.jinja2
```
This component generates commands using a LLM based on the given prompt file and should be included in the `pipeline` section of the `config.yml` file.

## E2E Test Results

The `e2e_tests` folder contains the test cases across different conversation categories that are used to evaluate the models.

The conversations are modelled using `flows` and the `domain` file contains the definition of bot utterances, slots, and actions that are used in the test cases.

The following are the results of the e2e tests conducted for different models using designated prompts. 

| Model   | Accuracy | Prompt file |
|---------|----------|-------------|
| gpt-4   | 88.09%   | default     |
| gpt-4-1106-preview | 71.42%      | default     |
| gpt-4-0125-preview | 67.86%      | default     |
| gpt-3.5-turbo | 63.1%      | data/prompts/gpt_3-5_turbo_cmd_gen_prompt.jinja2     |
| gpt-3.5-turbo-1106 | 52.38%      | data/prompts/gpt_3-5_turbo_1106_cmd_gen_prompt.jinja2     |
| mistral-medium | 44.05%      | data/prompts/mistral_medium_cmd_gen_prompt.jinja2     |
