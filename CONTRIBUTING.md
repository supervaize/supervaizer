# Contributing to SUPERVAIZER

Thank you for considering contributing to SUPERVAIZER! This document outlines the process for contributing to the project.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

- Check if the bug has already been reported
- Use the bug report template when opening an issue
- Include detailed steps to reproduce the bug
- Specify your environment (Python version, OS, etc.)

### Suggesting Features

- Check if the feature has already been suggested
- Use the feature request template when opening an issue
- Clearly describe the feature and its benefits
- Consider how it fits with the project's scope

### Pull Requests

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Setup

```bash
# Clone the repository
git clone [repository-url]
cd supervaizer

# Install development dependencies
uv venv
uv pip install -e ".[dev]"

# Run tests
pytest
```

## Coding Standards

- Follow PEP 8 conventions
- Use type hints for function parameters and return values
- Create proper docstrings with descriptions and parameter details
- Classes use PascalCase, functions/variables use snake_case
- Inherit from SvBaseModel (Pydantic) for data models
- Use loguru for logging with appropriate context binding
- Handle exceptions with ApiError class, capturing details

## Commit Message Guidelines

We follow the [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification for commit messages.

Talk imperative: Follow this rule: If applied, this commit will <commit message>

The commit message should be structured as follows:

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Changes that do not affect code functionality
- `refactor`: Code changes that neither fix bugs nor add features
- `test`: Adding or modifying tests
- `chore`: Changes to build process or auxiliary tools

## Testing

- Use pytest
- Write unit tests for all new features and bug fixes
- Maintain or improve code coverage
- Run the test suite before submitting PRs

## License

By contributing to SUPERVAIZER, you agree that your contributions will be licensed under the project's [Mozilla Public License 2.0](LICENSE).
