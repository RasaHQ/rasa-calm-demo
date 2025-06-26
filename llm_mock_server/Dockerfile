# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.2
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Set the working directory in the container
WORKDIR /app

# Copy only the dependency files to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install project dependencies and remove cache
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-dev \
    && rm -rf $POETRY_CACHE_DIR \
    && rm -rf /root/.cache/pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
# Copy the rest of the application code
COPY . .

#
RUN poetry build -f wheel -n && \
  pip install --no-deps dist/*.whl && \
  rm -rf dist *.egg-info

WORKDIR /app

# Remove copied files
RUN rm -rf /build

# Copy the collection file
COPY collection.json /app

# Make port 8000 available to the world outside this container
EXPOSE 8080

ENTRYPOINT ["llm-mock-server"]

# Run the application when the container launches
CMD ["-c", "/app/collection.json", "-p", "8080"]
