#!/bin/sh
# Known vulnerabilities in the dependencies of pip_requirements.txt (pip-audit,
# latest version through uvx). Runs the same way locally.
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
uvx pip-audit --requirement pip_requirements.txt --strict
