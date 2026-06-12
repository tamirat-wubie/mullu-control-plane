#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <owner> <repo> <branch> <policy-json>" >&2
  exit 2
fi

owner="$1"
repo="$2"
branch="$3"
policy_json="$4"

: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

curl -fsSL \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${owner}/${repo}/branches/${branch}/protection" \
  --data-binary "@${policy_json}"
