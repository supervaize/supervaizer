set dotenv-load := true
set export
set shell := ["bash", "-uc"]
nowts:=`date +%Y%m%d_%H%M%S`
YYYYMMDD:= `date +%Y%m%d`


# Development
# Show all available commands (default)
default:
    @just --list

# Install dev dependencies
install-dev:
    uv sync --extra dev

# Run pre-commit hooks manually
precommit:
    uv run python -m pre_commit run --all-files --verbose

# Run pre-commit autoupdate (when pre-commit-config.yaml is updated)
precommit-autoupdate:
    uv run python -m pre_commit autoupdate

# Run tests with coverage
test-cov *args:
    pytest --cov=supervaizer --cov-report=term --cov-report=html {{args}}


# Run tests without coverage
test *args:
    uv run pytest --no-cov {{args}}

# Run tests without coverage
test-no-cov *args:
    uv run pytest --no-cov {{args}}

# Run only previously failed tests
test-failed:
    uv run pytest --lf --no-cov

# Run mypy type checking
mypy:
    uv run python -m pre_commit run mypy --all-files

# Sync dependencies (from pyproject.toml)
install:
    uv sync

upgrade:
    uv sync -U

# Sync all dependencies - including dev dependencies
install-all:
    uv sync --all-extras

# build
build:
    hatch build

# Toggle PEP 440 .dev0 on canonical version (syncs src/supervaizer/__version__.py + pyproject [tool.bumpversion]).
# Does not edit CHANGELOG or historical docs. After `on`, avoid `just tag_version` until `off` (tags should be release-only).
# Usage: just version-dev on | just version-dev off
version-dev cmd:
    uv run python tools/dev_version.py {{cmd}}

# Reusable recipe to bump version
_bump-version bump_type:
    @echo "VERSION BUMP IN CICD - not running: hatch version {{bump_type}} "
    hatch build

# Increase 0.0.1
release-patch:
    just _bump-version fix

# Increase 0.1.0
release-minor:
    just _bump-version minor

# Increase 1.0.0
release-major:
    just _bump-version major

# Push tags to remote
push_tags:
    git push origin --tags
    @echo "Tags pushed to remote"

# Install Git hooks
install-hooks:
    # First unset any existing hooksPath
    @git config --unset-all core.hooksPath || true
    # Install pre-commit hooks
    @uv run python -m pre_commit install
    # Set up our custom hooks
    @git config core.hooksPath .githooks
    # Git hooks installed

# API documentation @http://127.0.0.1:8000/redoc
dev:
    uvicorn controller:app --reload

# Local test mode: no Studio credentials, built-in Hello World agent (for agent workbench)
local:
    uv run supervaizer start --local

# Create git tag for current version - Automated done in post-commit hook
tag-version:
    bash -c "VERSION=\$(grep '^VERSION = ' src/supervaizer/__version__.py | cut -d'\"' -f2) && TAG=\"v\${VERSION}\" && if git rev-parse -q --verify \"refs/tags/\${TAG}\" >/dev/null; then echo \"Tag \${TAG} already exists - skipping\"; else git tag -a \"\${TAG}\" -m \"Version \${VERSION}\" && echo \"Created tag \${TAG}\"; fi"

# Generate RSA private key (PEM) for SUPERVAIZER_PRIVATE_KEY (e.g. Vercel env)
generate-private-key:
    uv run python -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; from cryptography.hazmat.backends import default_backend; k = rsa.generate_private_key(65537, 2048, default_backend()); print(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())"

# Check git history for secret leaks
security-scan:
    trufflehog git file://. --results=verified,unknown --fail

# Generate model reference documentation
generate-docs:
    uv run python tools/gen_model_docs.py
    uv run python tools/export_openapi.py


# Deployment sequence
ready-to-go:
    just test-no-cov
    just precommit
    just version-dev off
    just generate-docs
    bash -euc 'branch_id="$(but status --json | uv run python tools/get_applied_but_branch_id.py)"; but commit "$branch_id" -m "chore: update documentation" --json --status-after'

# Merge develop to main
merge-to-main:
    @echo "Switching to main branch..."
    git checkout main
    @echo "Pulling latest main..."
    git pull origin main
    @echo "Merging develop into main..."
    git merge develop --no-ff -m "chore: merge develop to main"
    @echo "✅ Merged develop to main"

# Push main branch to remote
push-main:
    @echo "Pushing main branch to remote..."
    git push origin main
    @echo "✅ Main branch pushed to remote"

# Complete release: merge develop to main, push main and tags
release:
    just merge-to-main
    just push-main
    just push_tags
    just gh-release
    @echo "✅ Release complete! Main branch and tags pushed to remote"

# Ship to production: precommit, merge develop→main, push (CI does the version bump)
# Embed bump type token ([MINOR]/[PATCH]/[MAJOR]) so CI picks up the right part.
# Run "ready-to-go" to ensure the documentation commit happens in the active stack only.
# Usage: just ship [patch|minor|major]
ship part="minor":
    #!/usr/bin/env bash
    set -euo pipefail
    just precommit
    BUMP_TOKEN=$(echo "{{part}}" | tr '[:lower:]' '[:upper:]')
    git checkout main
    git pull origin main
    git merge develop --no-ff -m "[${BUMP_TOKEN}] chore: merge develop to main"
    git push origin main

# Create or update GitHub release for the latest tag on origin/main
gh-release:
    bash tools/gh-release-latest-tag.sh supervaize/supervaizer

# After `just ship`, wait for the GitHub release to be published, then
# merge main back into develop and refresh release notes from CHANGELOG.md.
ship-reconcile repo="supervaize/supervaizer" mode="merge" timeout_seconds="600" poll_seconds="10":
    bash tools/reconcile-release-after-ship.sh "{{repo}}" --mode "{{mode}}" --timeout-seconds {{timeout_seconds}} --poll-seconds {{poll_seconds}}
