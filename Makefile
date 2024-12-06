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

rasa-run-voice: .EXPORT_ALL_VARIABLES
	rasa inspect --voice --debug

rasa-train: .EXPORT_ALL_VARIABLES
	rasa train -c config/config.yml -d domain --data data

rasa-train-multistep: .EXPORT_ALL_VARIABLES
	rasa train -c config/multistep-config.yml -d domain --data data

rasa-train-qdrant: .EXPORT_ALL_VARIABLES
	rasa train -c config/qdrant-config.yml -d domain --data data

rasa-actions:
	rasa run actions

rasa-test-passing: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests/passing

rasa-test-flaky: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests/flaky

rasa-test-failing: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests/failing

rasa-test-multistep: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests/multistep

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
	poetry run rasa test e2e e2e_tests/passing

test-flaky: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/flaky

test-failing: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/failing

test-multistep: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/multistep

test-one: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e $(target) --debug

stop-duckling:
	docker stop duckling_container
