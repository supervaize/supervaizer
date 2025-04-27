# Contributing to SUPERVAIZER

Thank you for considering contributing to SUPERVAIZER! This document outlines the development process and guidelines.

## Development Environment

This project uses [just](https://github.com/casey/just) as a command runner. Here are the available commands:

```bash
just -l
```

### Setup Development Environment

1. Clone the repository
2. Install uv: `pip install uv`
3. Create and activate a virtual environment:
   - `uv venv`
   - Windows: `.venv\Scripts\activate`
   - Unix/MacOS: `source .venv/bin/activate`
4. Install development dependencies: `uv pip install -e ".[dev]"` or `just dev-install`
5. Install Git hooks: `just install-hooks`

### Running Tests

```bash
pytest
```

Or for specific test categories:

```bash
pytest -m "not slow"  # Skip slow tests
pytest -m "current"   # Run tests under development
```

Running tests without test coverage:

```bash
just test-no-cov
```

Rerunning failed tests:

```bash
just test-failed
```

### Type checking

Running mypy directly:

```bash
mypy supervaizer
```

Running mypy for all (including tests):

```bash
mypy supervaizer tests
```

Running mypy via pre-commit:

```bash
just mypy
```

## Pull Request Process

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the tests to ensure they pass
5. Update documentation as needed
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Code Style

We follow PEP 8 with a line length of 120 characters. The project uses the following tools for code quality:

- Ruff for code formatting, linting and import sorting
- Mypy for type checking

All of these are run as pre-commit hooks, so make sure you install them as mentioned above.

## License

By contributing, you agree that your contributions will be licensed under the project's [Mozilla Public License 2.0](LICENSE.md).
