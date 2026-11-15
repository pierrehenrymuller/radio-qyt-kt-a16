#!/bin/sh
# The wheel and the source archive build, the wheel installs in a fresh venv and
# starts. Runs the same way locally.
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
. .github/python.sh
make package PYTHON_VERSION="$python"
