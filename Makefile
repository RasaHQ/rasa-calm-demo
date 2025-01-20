.PHONY: install test run train test-passing help actions

-include .env

help:
	@echo "install - install dependencies"
	@echo "test - run tests"
	@echo "run - run chatbot"
	@echo "train - train chatbot"

.EXPORT_ALL_VARIABLES:

# ---------------------------------------------------
# rasa based targets

rasa-test: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests

rasa-run: .EXPORT_ALL_VARIABLES
	rasa inspect --debug

rasa-train: .EXPORT_ALL_VARIABLES
	rasa train -c config.yml -d domain --data data

rasa-actions:
	rasa run actions

rasa-e2e-test: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests

rasa-du-test: .EXPORT_ALL_VARIABLES
	rasa test du dialogue_understanding_tests

rasa-test-one: .EXPORT_ALL_VARIABLES
	rasa test e2e $(target) --debug

# ---------------------------------------------------
# poetry based targets

install:
	poetry run python3 -m pip install -U pip
	poetry install

run-duckling:
	docker run --rm --name duckling_container -d -p 8000:8000 rasa/duckling

test: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests

run: .EXPORT_ALL_VARIABLES run-duckling
	poetry run rasa inspect --debug

train: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/config.yml -d domain --data data

train-multistep: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/multistep-config.yml -d domain --data data

train-qdrant: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/qdrant-config.yml -d domain --data data

actions:
	poetry run rasa run actions

test-passing: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/passing --e2e-results

test-flaky: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/flaky --e2e-results

test-failing: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/failing --e2e-results

test-multistep: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/multistep --e2e-results

test-one: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e $(target) --debug

stop-duckling:
	docker stop duckling_container

test-passing-assertions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_assertions/passing --e2e-results

test-flaky-assertions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_assertions/flaky --e2e-results

test-failing-assertions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_assertions/failing --e2e-results

make test-passing-stub-custom-actions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_stub_custom_actions/passing --e2e-results
