#!/bin/sh
# Known vulnerabilities in the dependencies of pip_requirements.txt (pip-audit,
# latest version through uvx). Runs the same way locally.
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
uvx pip-audit --requirement pip_requirements.txt --strict
