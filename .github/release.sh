#!/bin/sh
# Release of a v* tag: wheel and source archive built in the Alpine image, then
# attached to a GitHub release (gh, GITHUB_TOKEN). Locally it only builds dist/.
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
rm -rf dist
podman run --rm -v "$PWD:/src:Z" -w /src ghcr.io/astral-sh/uv:alpine \
    uv build --out-dir dist
ls -l dist
if [ -n "${GITHUB_ACTIONS:-}" ]; then
    gh release create "$GITHUB_REF_NAME" dist/* --generate-notes \
        --title "$GITHUB_REF_NAME"
fi
