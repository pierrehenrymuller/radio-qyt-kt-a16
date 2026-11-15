#!/bin/sh
# Everything the push workflows check, in one run (local use).
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
sh .github/tests.sh
sh .github/build.sh
sh .github/audit.sh
