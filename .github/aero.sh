#!/bin/sh
# Rebuild kta16/aero.json from the SIA eAIP of the current AIRAC cycle (network).
# Fails when the SIA pages or the VAC layout changed (see kta16/aero.py).
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
. .github/python.sh
make venv PYTHON_VERSION="$python"
make aero
git diff --stat -- kta16/aero.json
