# Use the official Python 3.10 Bullseye base image for devcontainers
FROM mcr.microsoft.com/devcontainers/python:1-3.10-bullseye

# Install required system libraries and dependencies
RUN apt-get update && apt-get install -y libhdf5-dev && rm -rf /var/lib/apt/lists/*

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Set the working directory and create the virtual environment
WORKDIR /workspaces/rasa

# Create the virtual environment using Python's built-in venv
# RUN python -m venv /workspaces/rasa/.venv

# Upgrade pip and install uv within the virtual environment
RUN pip install --upgrade pip uv

# Ensure the virtual environment is activated by default
# ENV PATH="/workspaces/rasa/.venv/bin:$PATH"

# Copy requirements file for Rasa Pro and dependencies
COPY ../qdrant-requirements.txt .

# Install Rasa Pro and dependencies in the virtual environment
RUN uv pip install --system --extra-index-url https://europe-west3-python.pkg.dev/rasa-releases/rasa-pro-python/simple rasa-pro==3.9.6 \
 && uv pip install --system -r qdrant-requirements.txt

# Expose the ports for Rasa and the Action Server
EXPOSE 5005
EXPOSE 5055
