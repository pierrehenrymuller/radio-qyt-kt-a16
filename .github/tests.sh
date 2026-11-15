#!/bin/sh
# Lint and tests with coverage (coverage.xml). Runs the same way locally.
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
. .github/python.sh
make venv PYTHON_VERSION="$python"
make lint
make coverage
