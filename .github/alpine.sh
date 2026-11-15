#!/bin/sh
# Run one of the scripts of .github in the Alpine image with the latest uv, as the
# GitHub runner does (podman on the Ubuntu runner; JavaScript actions stay on the
# host). Usage: sh .github/alpine.sh .github/tests.sh
set -eu
# shellcheck disable=SC3040  # busybox ash (Alpine) and bash have pipefail
set -o pipefail

cd "$(dirname "$0")/.."
podman run --rm -e CI_LATEST_PYTHON="${CI_LATEST_PYTHON:-}" \
    -v "$PWD:/src:Z" -w /src ghcr.io/astral-sh/uv:alpine sh "$1"
