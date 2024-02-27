# Prompts README

This README provides information on how to use the prompts and includes the results of the end-to-end (e2e) tests for different models.

## Usage

```
name: LLMCommandGenerator
prompt: path_to_prompt_file.jinja2
```

## E2E Test Results

The following are the results of the e2e tests conducted for different models using designated prompts:

| Model   | Accuracy | Prompt file |
|---------|----------|-------------|
| gpt-4   | 88.09%   | default     |
| gpt-4-1106-preview | 71.42%      | default     |
| gpt-4-0125-preview | 67.86%      | default     |
| gpt-3.5-turbo | 63.1%      | data/prompts/gpt_3-5_turbo_cmd_gen_prompt.jinja2     |
| gpt-3.5-turbo-1106 | 52.38%      | data/prompts/gpt_3-5_turbo_1106_cmd_gen_prompt.jinja2     |
| mistral-medium | 44.05%      | data/prompts/mistral_medium_cmd_gen_prompt.jinja2     |
