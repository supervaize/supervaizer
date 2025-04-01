set dotenv-load := true
set export
set shell := ["bash", "-uc"]
nowts:=`date +%Y%m%d_%H%M%S`
YYYYMMDD:= `date +%Y%m%d`


# Development
# Show all available commands (default)
default:
    @just --list

# Run pre-commit hooks manually
pre-commit-manual:
    pre-commit run --all-files --verbose

# Run pre-commit autoupdate (when pre-commit-config.yaml is updated)
pre-commit-autoupdate:
    pre-commit autoupdate

# Run tests without coverage
test-no-cov:
    pytest --no-cov

# Sync dependencies
env_sync:
    uv sync

# build
build:
    hatch build

# Increase 0.0.1
build_fix:
    hatch version fix
    hatch build

# Increase 0.1.0
build_minor:
    hatch version minor
    hatch build

# Increase 1.0.0
build_major:
    hatch version major
    hatch build


# API documentation @http://127.0.0.1:8000/redoc
unicorn:
    uvicorn controller:app --reload

#
