#!/bin/bash
set -e

# Change to app directory
cd /app

# Remove any stale .venv references that might cause issues
if [ -d ".venv" ] && [ ! -f ".venv/bin/python3" ]; then
    rm -rf .venv
fi

# Install the project if not already installed
# This ensures the supervaizer command is available
if ! command -v supervaizer &> /dev/null; then
    echo "Installing supervaizer..."
    uv sync --frozen --no-dev
fi

# Run supervaizer start
exec uv run supervaizer start
