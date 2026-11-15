#!/bin/sh
# Secrets in the whole git history (gitleaks). There is none today: the check is
# there for the day one slips in. In GitHub Actions it runs in the gitleaks image;
# locally, without gitleaks installed, the same image runs through podman.
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
if command -v gitleaks >/dev/null 2>&1; then
    gitleaks git --redact --verbose .
else
    podman run --rm -v "$PWD:/repo:ro,z" ghcr.io/gitleaks/gitleaks:latest \
        git --redact --verbose /repo
fi
