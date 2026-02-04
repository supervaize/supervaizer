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
    uv run pre-commit run --all-files --verbose

# Run pre-commit autoupdate (when pre-commit-config.yaml is updated)
precommit-autoupdate:
    uv run pre-commit autoupdate

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
    uv run pre-commit run mypy --all-files

# Sync dependencies (from pyproject.toml)
env_sync:
    uv sync

# Sync all dependencies - including dev dependencies
env_sync_all:
    uv sync --all-extras

# build
build:
    hatch build

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
    @uv run pre-commit install
    # Set up our custom hooks
    @git config core.hooksPath .githooks
    # Git hooks installed

# API documentation @http://127.0.0.1:8000/redoc
unicorn:
    uvicorn controller:app --reload

# Create git tag for current version - Automated done in post-commit hook
tag_version:
    bash -c "VERSION=\$(grep '^VERSION = ' src/supervaizer/__version__.py | cut -d'\"' -f2) && git tag -a \"v\${VERSION}\" -m \"Version \${VERSION}\" && echo \"Created tag v\${VERSION}\""

# Generate RSA private key (PEM) for SUPERVAIZER_PRIVATE_KEY (e.g. Vercel env)
generate-private-key:
    uv run python -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; from cryptography.hazmat.backends import default_backend; k = rsa.generate_private_key(65537, 2048, default_backend()); print(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())"

# Check git history for secret leaks
trufflehog_scan_git_history:
    trufflehog git file://. --results=verified,unknown --fail

# Generate model reference documentation
generate_documentation:
    python tools/gen_model_docs.py
    python tools/export_openapi.py


# Deployment sequence
ready-to-go:
    just test-no-cov
    just precommit
    just build_fix
    just generate_documentation
    git add . && git commit -m "chore: update documentation"
    just tag_version

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
    @echo "✅ Release complete! Main branch and tags pushed to remote"
