#!/bin/sh
# The wheel and the source archive build, the wheel installs in a fresh venv and
# starts. Runs the same way locally.
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
. .github/python.sh
make package PYTHON_VERSION="$python"
