# Contributing to Supervaizer

Thank you for considering contributing to Supervaizer. This document outlines the development process and guidelines.

## Development Environment

This project uses [just](https://github.com/casey/just) as a command runner and [uv](https://docs.astral.sh/uv/) for Python environments. List all recipes with:

```bash
just
```

### Setup

1. Clone the repository and branch from `develop`.
2. Install uv (`pip install uv` or `brew install uv`).
3. Install development dependencies: `just install-dev`
4. Install Git hooks: `just install-hooks`

`uv run <cmd>` runs a command inside the project environment; no manual virtualenv activation is needed.

### Running Tests

```bash
just test              # full suite, no coverage
just test-cov          # with coverage report
just test-failed       # rerun last failures
```

### Type Checking and Linting

```bash
just precommit         # ruff check + ruff format + mypy + hooks, all files
just mypy              # mypy only (same invocation as CI)
uv run mypy src/supervaizer tests   # include tests
```

## Pull Request Process

1. Fork the repository and create a branch from `develop` (`git switch -c feature/amazing-feature develop`).
2. Make your changes and add or update targeted tests.
3. Run `just test` and `just precommit`.
4. Update documentation (`docs/CHANGELOG.md` **Unreleased** section, and `just generate-docs` if public models changed).
5. Commit with a signed-off Conventional Commit message: `git commit -s -m "✨ feat: add amazing feature"`. The pre-commit hooks enforce the [gitmoji conventional](https://github.com/ljnsn/cz-conventional-gitmoji) format.
6. Push and open a Pull Request against `develop`. `main` only receives release PRs.

## Code Style

- Ruff for formatting and linting (default 88-column line length, `preview` formatting enabled).
- Mypy for type checking. New or modified functions, including tests, need explicit type annotations and return types.
- Module-level imports by default; document any unavoidable local import.
- Supervaizer is a published SDK: keep public payloads backward compatible unless the change is explicitly breaking and coordinated with Studio.

Run `just precommit` before pushing; CI enforces the same checks on every pull request.

## Licensing and Contribution Terms

By submitting a contribution (code, documentation, or other content) to this project, you agree to license it under the terms of the Mozilla Public License 2.0 (MPL-2.0).

You retain the copyright to your contribution, but you grant the project maintainers and all users the right to use, modify, and distribute it as part of the project under the MPL-2.0 license.

This project uses the Developer Certificate of Origin (DCO). By submitting a contribution, you certify that:

> I certify that the contribution was created in whole or in part by me and I have the right to submit it under the MPL-2.0 license.

Express this certification by signing off each commit with `git commit -s`. Contributions without this sign-off may be rejected.
