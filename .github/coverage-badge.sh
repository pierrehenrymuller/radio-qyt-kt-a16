#!/bin/sh
# Coverage badge without a third-party service: a shields.io "endpoint" JSON file,
# pushed by GitHub Actions on the "badges" branch with the GITHUB_TOKEN of the run.
# Locally (no GITHUB_ACTIONS) it only prints the JSON.
set -eu
# pipefail where the shell has it (bash, busybox ash; dash, the sh of the Ubuntu runner, has not)
# shellcheck disable=SC3040
(set -o pipefail) 2>/dev/null && set -o pipefail

cd "$(dirname "$0")/.."
pct=$(python3 -c 'import xml.etree.ElementTree as E; print(round(float(E.parse("coverage.xml").getroot().get("line-rate")) * 100))')
color=red
[ "$pct" -ge 60 ] && color=yellow
[ "$pct" -ge 80 ] && color=brightgreen
json="{\"schemaVersion\": 1, \"label\": \"coverage\", \"message\": \"$pct%\", \"color\": \"$color\"}"
if [ -z "${GITHUB_ACTIONS:-}" ]; then
    echo "$json"
    exit 0
fi
tmp=$(mktemp -d)
git -C "$tmp" init -q -b badges
printf '%s\n' "$json" >"$tmp/coverage.json"
git -C "$tmp" add coverage.json
git -C "$tmp" -c user.name="github-actions[bot]" \
    -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -q -m "coverage $pct%"
# one commit only: the branch holds the latest value, nothing else
git -C "$tmp" push -q --force \
    "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" badges
