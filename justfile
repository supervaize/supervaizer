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
    pre-commit run --all-files --verbose

# Run pre-commit autoupdate (when pre-commit-config.yaml is updated)
precommit-autoupdate:
    pre-commit autoupdate

# Run tests without coverage
test-no-cov:
    pytest --no-cov

# Run only previously failed tests
test-failed:
    pytest --lf --no-cov

# Run mypy type checking
mypy:
    pre-commit run mypy --all-files

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
    hatch version {{bump_type}}
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
    @pre-commit install
    # Set up our custom hooks
    @git config core.hooksPath .githooks
    # Git hooks installed

# API documentation @http://127.0.0.1:8000/redoc
unicorn:
    uvicorn controller:app --reload

# Create git tag for current version - Automated done in post-commit hook
tag_version:
    bash -c "VERSION=\$(grep '^VERSION = ' src/supervaizer/__version__.py | cut -d'\"' -f2) && git tag -a \"v\${VERSION}\" -m \"Version \${VERSION}\" && echo \"Created tag v\${VERSION}\""


# Generate model reference documentation
generate_model_docs:
    python tools/gen_model_docs.py