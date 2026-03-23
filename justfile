set dotenv-load := true
set export
set shell := ["bash", "-uc"]
nowts:=`date +%Y%m%d_%H%M%S`
YYYYMMDD:= `date +%Y%m%d`


# Development
# Show all available commands (default)
default:
    @just --list

# Dev install
dev-install:
    uv venv
    uv pip install -e .[dev]

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
env_sync:
    uv sync

# Sync all dependencies - including dev dependencies
env_sync_all:
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
_bump_version bump_type:
    @echo "VERSION BUMP IN CICD - not running: hatch version {{bump_type}} "
    hatch build

# Increase 0.0.1
build_fix:
    just _bump_version fix

# Increase 0.1.0
build_minor:
    just _bump_version minor

# Increase 1.0.0
build_major:
    just _bump_version major

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
unicorn:
    uvicorn controller:app --reload

# Local test mode: no Studio credentials, built-in Hello World agent (for agent workbench)
local:
    uv run supervaizer start --local

# Create git tag for current version - Automated done in post-commit hook
tag_version:
    bash -c "VERSION=\$(grep '^VERSION = ' src/supervaizer/__version__.py | cut -d'\"' -f2) && TAG=\"v\${VERSION}\" && if git rev-parse -q --verify \"refs/tags/\${TAG}\" >/dev/null; then echo \"Tag \${TAG} already exists - skipping\"; else git tag -a \"\${TAG}\" -m \"Version \${VERSION}\" && echo \"Created tag \${TAG}\"; fi"

# Generate RSA private key (PEM) for SUPERVAIZER_PRIVATE_KEY (e.g. Vercel env)
generate-private-key:
    uv run python -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; from cryptography.hazmat.backends import default_backend; k = rsa.generate_private_key(65537, 2048, default_backend()); print(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())"

# Check git history for secret leaks
trufflehog_scan_git_history:
    trufflehog git file://. --results=verified,unknown --fail

# Generate model reference documentation
generate_documentation:
    uv run python tools/gen_model_docs.py
    uv run python tools/export_openapi.py


# Deployment sequence
ready-to-go:
    just test-no-cov
    just precommit
    just version-dev off
    just generate_documentation
    bash -euc 'branch_id="$(but status --json | uv run python tools/get_applied_but_branch_id.py)"; but commit "$branch_id" -m "chore: update documentation" --json --status-after'

# Merge develop to main - after just tag_version
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

# Create or update GitHub release for the latest tag on origin/main
gh-release:
    bash tools/gh-release-latest-tag.sh supervaize/supervaizer
