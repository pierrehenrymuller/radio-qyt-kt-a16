#!/bin/sh
# Rebuild kta16/aero.json from the SIA eAIP of the current AIRAC cycle (network).
# Fails when the SIA pages or the VAC layout changed (see kta16/aero.py).
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
. .github/python.sh
make venv PYTHON_VERSION="$python"
make aero
git diff --stat -- kta16/aero.json
