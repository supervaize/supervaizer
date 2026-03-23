#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${1:-supervaize/supervaizer}"

echo "Fetching latest tags from origin..."
git fetch origin --tags

LATEST_TAG="$(git describe --tags --abbrev=0 origin/main)"

if [ -z "${LATEST_TAG}" ]; then
  echo "❌ No tags found on origin/main. Aborting."
  exit 1
fi

echo "Using latest tag on origin/main: ${LATEST_TAG}"

# Find previous tag (for release notes range)
PREV_TAG="$(git tag --merged origin/main --sort=-creatordate | grep -v "^${LATEST_TAG}$" | head -1 || true)"

if gh release view "${LATEST_TAG}" --repo "${REPO_SLUG}" >/dev/null 2>&1; then
  echo "GitHub release ${LATEST_TAG} already exists. Marking as latest..."
  gh release edit "${LATEST_TAG}" \
    --repo "${REPO_SLUG}" \
    --latest
  echo "✅ GitHub release ${LATEST_TAG} updated as latest"
else
  echo "Creating GitHub release ${LATEST_TAG}..."
  if [ -n "${PREV_TAG}" ]; then
    gh release create "${LATEST_TAG}" \
      --repo "${REPO_SLUG}" \
      --title "${LATEST_TAG}" \
      --latest \
      --generate-notes \
      --notes-start-tag "${PREV_TAG}"
  else
    # First release: no previous tag
    gh release create "${LATEST_TAG}" \
      --repo "${REPO_SLUG}" \
      --title "${LATEST_TAG}" \
      --latest \
      --generate-notes
  fi
  echo "✅ GitHub release ${LATEST_TAG} created"
fi
