.PHONY: install test run train test-passing help actions

-include .env

help:
	@echo "install - install dependencies"
	@echo "test - run tests"
	@echo "run - run chatbot"
	@echo "train - train chatbot"

.EXPORT_ALL_VARIABLES:

install:
	poetry run python -m pip install -U pip
	poetry install

test: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests

run: .EXPORT_ALL_VARIABLES
	poetry run rasa inspect --debug

train: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config.yml -d domain --data data

actions:
	poetry run rasa run actions

test-passing: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/passing

test-flaky: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/flaky

test-failing: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/failing

test-one: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e $(target) --debug
