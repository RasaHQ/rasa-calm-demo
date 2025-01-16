#!/usr/bin/env bash
set -eu pipefail

RASA_CALM_DEMO_BRANCH="$(git branch --show-current)"
RASA_PRO_VERSION="$(rasa --version | grep 'Rasa Pro Version' | tr -d ' ' | awk -F ':' '{print $2}')"
RASA_CALM_DEMO_SHA="$(git rev-parse --short HEAD)"

echo "RASA_CALM_DEMO_BRANCH=${RASA_CALM_DEMO_BRANCH}"
echo "RASA_PRO_VERSION=${RASA_PRO_VERSION}"
echo "RASA_CALM_DEMO_SHA=${RASA_CALM_DEMO_SHA}"

OTEL_RESOURCE_ATTRIBUTES=rasa-pro-version="${RASA_PRO_VERSION}",rasa-calm-demo-sha="${RASA_CALM_DEMO_SHA}",rasa-calm-demo-branch="${RASA_CALM_DEMO_BRANCH}"
echo "OTEL_RESOURCE_ATTRIBUTES=${OTEL_RESOURCE_ATTRIBUTES}"

export RASA_CALM_DEMO_BRANCH
export RASA_PRO_VERSION
export OTEL_RESOURCE_ATTRIBUTES
