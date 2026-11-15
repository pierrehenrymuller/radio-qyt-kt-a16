#!/bin/sh
# Sourced by the other scripts: tools of the Alpine image, then the Python to use.
# CI_LATEST_PYTHON=1: the latest stable Python 3, else .python-version.
if command -v apk >/dev/null 2>&1; then
    apk add --no-cache make git >/dev/null
fi
if [ -n "${CI_LATEST_PYTHON:-}" ]; then
    # "3": the latest Python 3, whatever .python-version says
    uv python install 3
    python="$(uv python find 3)"
else
    python="$(cat .python-version)"
fi
echo "Python: $python"
