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

rasa-train: .EXPORT_ALL_VARIABLES
	rasa train -c config/config.yml -d domain --data data

rasa-train-qdrant: .EXPORT_ALL_VARIABLES
	rasa train -c config/qdrant-config.yml -d domain --data data

rasa-actions:
	rasa run actions

rasa-run: .EXPORT_ALL_VARIABLES
	rasa inspect --debug

rasa-test: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests_with_assertions

rasa-test-one: .EXPORT_ALL_VARIABLES
	rasa test e2e $(target) --debug

# ---------------------------------------------------
# poetry based targets

install:
	poetry run python3 -m pip install -U pip
	poetry install

run-duckling:
	docker run --rm --name duckling_container -d -p 8000:8000 rasa/duckling

train: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/config.yml -d domain --data data

train-qdrant: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/qdrant-config.yml -d domain --data data

actions:
	poetry run rasa run actions

run: .EXPORT_ALL_VARIABLES run-duckling
	poetry run rasa inspect --debug

test: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_assertions

test-one: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e $(target) --debug

stop-duckling:
	docker stop duckling_container

test-passing-stub-custom-actions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests_with_stub_custom_actions/passing --e2e-results

test-repeat-command: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/repeat --e2e-results