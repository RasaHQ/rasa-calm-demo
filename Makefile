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

rasa-train-search-ready: .EXPORT_ALL_VARIABLES
	rasa train -c config/search-ready-config.yml -d domain --data data

rasa-train-qdrant: .EXPORT_ALL_VARIABLES
	rasa train -c config/qdrant-config.yml -d domain --data data

rasa-actions:
	rasa run actions

rasa-run: .EXPORT_ALL_VARIABLES
	rasa inspect --debug

rasa-test: .EXPORT_ALL_VARIABLES
	rasa test e2e e2e_tests/tests_for_default_config

rasa-test-one: .EXPORT_ALL_VARIABLES
	rasa test e2e $(target) --debug

# ---------------------------------------------------
# poetry based targets

install:
	poetry run python3 -m pip install -U pip
	poetry install

run-duckling:
	docker run --rm --name duckling_container -d -p 8000:8000 rasa/duckling

run-mock-llm-server:
	docker compose -f llm_mock_server/docker-compose.yml up --wait

build-and-run-mock-llm-server-in-watch-mode-for-local-development:
	docker compose -f llm_mock_server/docker-compose.yml up --build --watch

train: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/config.yml -d domain --data data

train-search-ready: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/search-ready-config.yml -d domain --data data

train-qdrant: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/qdrant-config.yml -d domain --data data

train-mock-llm-server: .EXPORT_ALL_VARIABLES
	poetry run rasa train -c config/config.yml -d domain --data data --endpoints mock-llm-server-endpoints.yml

actions:
	poetry run rasa run actions

run: .EXPORT_ALL_VARIABLES run-duckling
	poetry run rasa inspect --debug

test: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/tests_for_default_config --coverage-report

test-stub-custom-actions: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/tests_with_stub_custom_actions --e2e-results

test-one: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e $(target) --debug

test-flows-with-mock-llm-server: .EXPORT_ALL_VARIABLES
	poetry run rasa test e2e e2e_tests/mock_llm_server --e2e-results --endpoints mock-llm-server-endpoints.yml --debug

stop-duckling:
	docker stop duckling_container
