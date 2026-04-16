#!/usr/bin/env bash
#
# Reconcile release after `just ship`:
# 1. Detect latest tag on `origin/main` vs latest tag on `origin/develop`.
# 2. Wait until the PyPI package version for that tag is published.
# 3. Merge (or rebase) `origin/main` back into `develop` and push `develop`.
# 4. Overwrite GitHub Release notes using the matching changelog section.
#
# This script is intentionally side-effecting (git merge/rebase + GitHub release edit),
# but it will refuse to run with a dirty working tree.

set -euo pipefail

REPO_SLUG="${1:-supervaize/supervaizer}"
shift || true

MODE="merge"
TIMEOUT_SECONDS=1800
POLL_SECONDS=15

DEVELOP_BRANCH="${DEVELOP_BRANCH:-develop}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
PYPI_PACKAGE="${PYPI_PACKAGE:-supervaizer}"
PYPI_BASE_URL="${PYPI_BASE_URL:-https://pypi.org/pypi}"

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --mode)
      MODE="${2}"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2}"
      shift 2
      ;;
    --poll-seconds)
      POLL_SECONDS="${2}"
      shift 2
      ;;
    *)
      echo "Unknown argument: ${1}" >&2
      exit 2
      ;;
  esac
done

if [[ "${MODE}" != "merge" && "${MODE}" != "rebase" ]]; then
  echo "Invalid --mode: ${MODE} (expected merge|rebase)" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit/stash before running this script." >&2
  exit 1
fi

echo "Fetching origin branches/tags..."
git fetch origin "${MAIN_BRANCH}" "${DEVELOP_BRANCH}" --tags

LATEST_TAG="$(git describe --tags --abbrev=0 "origin/${MAIN_BRANCH}" 2>/dev/null || true)"
DEV_TAG="$(git describe --tags --abbrev=0 "origin/${DEVELOP_BRANCH}" 2>/dev/null || true)"

if [[ -z "${LATEST_TAG}" ]]; then
  echo "❌ Could not determine latest tag on origin/${MAIN_BRANCH}. Aborting." >&2
  exit 1
fi

if [[ "${LATEST_TAG}" == "${DEV_TAG}" ]]; then
  echo "No new version detected on origin/${MAIN_BRANCH} (latest: ${LATEST_TAG}) compared to origin/${DEVELOP_BRANCH}."
  exit 0
fi

echo "Detected new release: ${LATEST_TAG} (develop had: ${DEV_TAG:-<none>})"

VERSION="${LATEST_TAG#v}"
echo "Waiting for PyPI publish: ${PYPI_PACKAGE}==${VERSION}..."
deadline_epoch="$(date +%s)"
deadline_epoch="$((deadline_epoch + TIMEOUT_SECONDS))"

is_pypi_published() {
  local pkg="$1"
  local version="$2"

  PYPI_BASE_URL="${PYPI_BASE_URL}" python -c '
import os, sys
from urllib.request import urlopen
from urllib.error import HTTPError

pkg = sys.argv[1]
version = sys.argv[2]
base = os.environ.get("PYPI_BASE_URL", "https://pypi.org/pypi")
url = f"{base}/{pkg}/{version}/json"
try:
    with urlopen(url, timeout=20) as r:
        if r.status != 200:
            sys.exit(1)
except HTTPError:
    sys.exit(1)
sys.exit(0)
' "${pkg}" "${version}"
}

while true; do
  if is_pypi_published "${PYPI_PACKAGE}" "${VERSION}"; then
    echo "✅ PyPI publish detected for ${PYPI_PACKAGE}==${VERSION}."
    break
  fi

  now_epoch="$(date +%s)"
  if (( now_epoch >= deadline_epoch )); then
    echo "❌ Timed out waiting for PyPI publish: ${PYPI_PACKAGE}==${VERSION}." >&2
    exit 1
  fi

  echo "  still waiting... (next check in ${POLL_SECONDS}s)"
  sleep "${POLL_SECONDS}"
done

echo "Syncing ${MAIN_BRANCH} -> ${DEVELOP_BRANCH} (${MODE})..."
git checkout "${DEVELOP_BRANCH}"
git pull --ff-only origin "${DEVELOP_BRANCH}"

if [[ "${MODE}" == "rebase" ]]; then
  git rebase "origin/${MAIN_BRANCH}"
else
  git merge --no-ff "origin/${MAIN_BRANCH}" -m "chore: sync ${MAIN_BRANCH} back to ${DEVELOP_BRANCH} (${LATEST_TAG})"
fi

echo "Pushing ${DEVELOP_BRANCH}..."
git push origin "${DEVELOP_BRANCH}"

echo "Extracting changelog notes for ${LATEST_TAG}..."

NOTES="$(python - <<PY
import re
from pathlib import Path

version = "${VERSION}"
path = Path("docs/CHANGELOG.md")
lines = path.read_text(encoding="utf-8").splitlines()

header_re = re.compile(rf'^## \\[{re.escape(version)}\\](?:\\s*-\\s*.*)?\\s*$')

start = None
for i, line in enumerate(lines):
    if header_re.match(line):
        start = i
        break

if start is None:
    raise SystemExit(f"Could not find changelog section header for version={version}")

end = len(lines)
for j in range(start + 1, len(lines)):
    if re.match(r'^## \\[', lines[j]):
        end = j
        break

block = "\\n".join(lines[start:end]).strip()
print(block)
PY
)"

if [[ -z "${NOTES// }" ]]; then
  echo "❌ Extracted empty changelog notes for version ${VERSION}. Aborting." >&2
  exit 1
fi

if gh release view "${LATEST_TAG}" --repo "${REPO_SLUG}" >/dev/null 2>&1; then
  echo "Updating existing GitHub release notes..."
  printf "%s\n" "${NOTES}" | gh release edit "${LATEST_TAG}" --repo "${REPO_SLUG}" --notes-file - --latest
else
  echo "Creating GitHub release (tag ${LATEST_TAG})..."
  printf "%s\n" "${NOTES}" | gh release create "${LATEST_TAG}" --repo "${REPO_SLUG}" --title "${LATEST_TAG}" --notes-file - --latest --verify-tag
fi

echo "✅ Reconcile complete for ${LATEST_TAG}."

