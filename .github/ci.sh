#!/bin/sh
# Everything the push workflows check, in one run (local use).
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
sh .github/tests.sh
sh .github/build.sh
sh .github/audit.sh
