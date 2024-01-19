#!/usr/bin/env python

"""This script builds and publishes a wheel from a Poetry project. Poetry has build and publish
capabilities, but this script does some additional things:
- It adds a timestamp as the patch version.
- It replaces local dependencies with published dependencies.
"""

import argparse
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import toml

def replace_local_versions() -> None:
    """
    Assumes there's a pyproject.toml file in the current working directory. This function
    adds a patch version, replaces local dependencies with published ones, and releases a
    wheel file to our local repository.
    """
    token = os.environ.get("GITHUB_TOKEN")

    pyproject_filename = "pyproject.toml"

    pyproject_data = toml.load(pyproject_filename)
    dependencies = pyproject_data["tool"]["poetry"].get("dependencies", [])

    dependencies["rasa"] = {}

    dependencies["rasa"] = {"git": "https://github.com/RasaHQ/rasa.git", "branch": "dm2"}
    dependencies["rasa-plus"] = {"git": f"https://oauth2:{token}@github.com/RasaHQ/rasa-plus.git", "branch": "dm2"}

    with open(pyproject_filename, "w") as output_file:
        toml.dump(pyproject_data, output_file)

if __name__ == "__main__":
    replace_local_versions()
