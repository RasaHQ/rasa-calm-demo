# Mock LLM server for deterministic E2E tests
Mock `OpenAI` API server, containing `v1/chat/completions` endpoints, that return pre-configured responses.

## Brief technical details
### Server setup
[`llm_mock_server.py`](./llm_mock_server.py) script sets up a `FastAPI` server, with endpoints created by parsing `Postman` collection [`collection.json`](./collection.json),
which contains endpoints with sample requests and corresponding pre-configured responses. The server can be started as a Docker container, listening on port 8080, via [`docker-compose.yml`](./docker-compose.yml).

### Requests routing
Requests (for example from E2E tests) are routed to relevant endpoint by matching against conversation history and last user message defined in endpoints' sample requests.

## Sample capabilities and how to add new tests
### Sample capabilities
As a brief example of some capabilities, the server can respond with following mock commands (using the DSL v2 used by the `CompactLLMCommandGenerator`):
1. `start flow add_contact`
2. `set slot add_contact_handle @barts`
3. `set slot add_contact_name Bart`
4. `set slot add_contact_confirmation True`
5. `start flow list_contacts`

### How to add further requests and responses
This can be done by updating the `Postman` collection [`collection.json`](./collection.json). Easiest way to do this is:
1. Prerequisites: 
    - If not done already, then install `Postman` locally (on `mac`: `brew install --cask postman`).
    - (Optional) Start Mock LLM server in watch mode by running `make` target 
    `make build-and-run-mock-llm-server-in-watch-mode-for-local-development`. This would automatically hot-reload the mock LLM server, once the collection is updated and saved, to serve responses from updated collection.
2. Import Collection into `Postman` (refer to Postman [docs](https://learning.postman.com/docs/getting-started/importing-and-exporting/importing-data/) for details), for viewing and editing.
3. Duplicate the endpoint(s) that is similar to your required request and response.
![alt text](./docs-images/image.png)
4. Edit the request and response bodies of the endpoint(s) accordingly.
![alt text](./docs-images/image-1.png)
5. Save the updated collection, and Export it to this repo directory, and commit + push changes.
![alt text](./docs-images/image-2.png)
