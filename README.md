# Rasa CALM Demo

`rasa-calm-demo` is a chatbot built with Rasa's LLM-native approach: [CALM](https://rasa.com/docs/rasa-pro/calm). 
The bot is used during the QA process of Rasa to test the CALM features and capabilities.

> [!CAUTION]
> Please note that the demo bot is an evolving platform. The flows currently 
> implemented in the demo bot are designed to showcase different features and 
> capabilities of the CALM bot. The functionality of each flow may vary, reflecting 
> CALM's current stage of development.

> [!IMPORTANT]
> `rasa-calm-demo` is not intended to show best practices for building a production-ready bot.

> [!NOTE]
> This demo bot is currently compatible with `3.13.0a1.dev6`.

## Terms of Use

This project is released under the Rasa's [Early Release Software Access Terms](https://rasa.com/early-release-software-terms/). 

## Demo Bot

The demo bot’s business logic is structured using Rasa’s 
[flows](https://rasa.com/docs/reference/primitives/flows/), rules, and stories, 
with functionality organized into several main skill groups. Some skill groups are 
implemented with the 
[Conversational AI with Language Models (CALM)](https://rasa.com/docs/learn/concepts/calm/) 
approach, defined through [flows](https://rasa.com/docs/reference/primitives/flows/), 
while others use the NLU-based method based on 
[training data](https://rasa.com/docs/reference/primitives/training-data-format). 
The [coexistence feature](https://rasa.com/docs/pro/calm-with-nlu/coexistence/)
enables both CALM and NLU-based systems to operate within a 
single assistant, providing flexible support for a range of conversational experiences. 
Each flow comprises a yaml file and an associated 
[domain](https://rasa.com/docs/reference/config/domain/) definition, detailing 
[actions](https://rasa.com/docs/reference/primitives/actions), 
[slots](https://rasa.com/docs/reference/primitives/slots), and 
[bot responses](https://rasa.com/docs/reference/primitives/responses).
The demo bot also demonstrates 
[enterprise search](https://rasa.com/docs/reference/config/policies/enterprise-search-policy) capabilities, 
such as answering questions using the [SQUAD dataset](https://huggingface.co/datasets/rajpurkar/squad). 
Additionally, the bot supports comprehensive 
[conversation repair](https://rasa.com/docs/learn/concepts/conversation-patterns/)
via Rasa’s default patterns, and provides examples of 
extending or overriding these patterns within the project.

## Running the project

This section guides you through the steps to get `rasa-calm-demo` bot up and running. 
We've provided simple `make` commands for a quick setup, as well as the underlying 
Rasa commands for a deeper understanding. Follow these steps to set up the 
environment, train your bot, launch the action server, start interactive sessions, 
and run end-to-end tests.

### Installation

> [!IMPORTANT]
> To build, run, and explore the bot's features, you need Rasa Pro license. You also 
> need access to the `rasa-pro` Python package. For installation instructions
> please refer our documentation [here](https://rasa.com/docs/pro/installation/overview).

> [!NOTE]
> If you want to check out the state of the demo bot compatible with earlier Rasa versions, 
> please check out the corresponding branch in the repository 
> (e.g. for Rasa 3.9.x: [3.9.x](https://github.com/RasaHQ/rasa-calm-demo/tree/3.9.x)).

Prerequisites:
- Rasa Pro license
- Python (3.10.12), e.g. using [pyenv](https://github.com/pyenv/pyenv): `pyenv install 3.10.12`
- Some flows require to set up and run [Duckling](https://github.com/facebook/duckling) server.
  The easiest option is to spin up a docker container using `docker run -p 8000:8000 rasa/duckling`.
  Alternatively, you can use the `make run-duckling` command locally.
  This runs automatically only when you use the `make run` command, before it launches the Inspector app.

After you cloned the repository, follow these installation steps:

1. Locate to the cloned repo:
   ```
   cd rasa-calm-demo
   ```
2. Set the python environment with `pyenv` or any other tool that gets you the right 
   python version
   ```
   pyenv local 3.10.12
   ```
3. Install the dependencies with `pip`
   ```
   pip install uv
   uv pip install rasa-pro --extra-index-url=https://europe-west3-python.pkg.dev/rasa-releases/rasa-pro-python/simple/
   ```
4. Create an environment file `.env` in the root of the project with the following 
   content:
   ```bash
   RASA_PRO_LICENSE=<your rasa pro license key>
   OPENAI_API_KEY=<your openai api key>
   RASA_DUCKLING_HTTP_URL=<url to the duckling server>
   ```

### Configuration

Check `config/config.yml` to make sure the [configuration](https://rasa.com/docs/reference/config/overview)
is appropriate before you train and run the bot.
There are some alternative configurations available in the `config` folder. 
Theses can be used via the appropriate `make` command during training.

### Training the bot

To train a model use `make` command for simplicity:
```commandline
make rasa-train
```
which is a shortcut for:
```commandline
rasa train -c config/config.yml -d domain --data data
```

The trained model is stored in `models` directory located in the project root.

### Starting the assistant

Before interacting with your assistant, start the action server to enable the 
assistant to perform [custom actions](https://rasa.com/docs/reference/primitives/custom-actions)
located in the `actions` directory. Start the action server with the `make` command:
```commandline
make rasa-actions
```
which is a shortcut for:
```commandline
rasa run actions
```

Once the action server is started, you have two options to interact with your trained
assistant:

1. **GUI-based interaction** using Rasa inspector:
```commandline
rasa inspect --debug
```

2. **CLI-based interaction** using Rasa shell:
```commandline
rasa shell --debug
```

### Running E2E tests

The demo bot comes with a set of [end-to-end (E2E) tests](https://rasa.com/docs/pro/testing/evaluating-assistant/).
You have the flexibility to run either all tests or a single specific test.

------

To run **all the tests** you can use the `make` command:
```commandline
make rasa-test
```
or
```commandline
rasa test e2e e2e_tests/tests_for_default_config
```

------

To run a **single test** with `make` command, you need to provide the path to a 
target test in an environment variable `target`:
```commandline
export target=e2e/tests/path/to/a/target/test.yml
```
and then run:
```commandline
make rasa-test-one
```
or
```commandline
rasa test e2e e2e/tests/path/to/a/target/test.yml
```

### Using Enterprise Search with Qdrant

To use the Enterprise Search capabilities with Qdrant, follow these steps:

1. Setup a local docker instance of Qdrant
   ```
   docker pull qdrant/qdrant
   docker run -p 6333:6333 -p 6334:6334 \
      -v $(pwd)/qdrant_storage:/qdrant/storage:z \
      qdrant/qdrant
   ```
2. Upload data to Qdrant
   - In your virtual environment where Rasa Pro is installed, also install these dependencies:
      ```
      pip install uv
      uv pip install -r qdrant-requirements.txt
      ```
   - Ingest documents from SQUAD dataset (modify the script if qdrant isn't running locally!)
      ```
      python scripts/load-data-to-qdrant.py
      ```
3. You can toggle parameter `use_generative_llm` in config.yml to change the behavior. 
   The answer is selected from the first search result -> metadata -> `answer` key

#### Custom Information Retriever

You can use a custom component for Information Retrieval by defining the custom component class 
name in the config as follows:

```
policies:
- name: FlowPolicy
- name: EnterpriseSearchPolicy
  vector_store:
  type: "addons.qdrant.Qdrant_Store"
```

This configuration refers to `addons/qdrant.py` file and the class `Qdrant_Store`. 
This class is also an example that information retrievers can use a custom query, note that in `search()` 
function the query is rewritten using the chat transcript by `prepare_search_query` function.
