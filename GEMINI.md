This is a Python project that provides a toolkit for building, managing, and connecting AI agents. It uses FastAPI for the web server, Typer for the command-line interface, and Pydantic for data validation. The project supports the Agent-to-Agent (A2A) and Agent Communication Protocol (ACP) for interoperability between AI agents.

### Building and Running

**1. Installation:**

The project's dependencies are listed in the `pyproject.toml` file. To install them, you can use the `just` command:

```bash
just dev-install
```

**2. Scaffolding:**

To get started, you can use the `scaffold` command to create a `supervaizer_control.py` file. This file is the main configuration file for your agent.

```bash
supervaizer scaffold
```

**3. Running the Server:**

Once you have configured your agent in `supervaizer_control.py`, you can start the server with the following command:

```bash
supervaizer start
```

**4. Testing:**

The project uses pytest for testing. To run the tests, use the following `just` command:

```bash
just test-no-cov
```

### Development Conventions

*   **Code Style:** The project uses `ruff` for linting and `black` for formatting. The configuration for these tools can be found in the `pyproject.toml` file.
*   **Type Hinting:** The project uses type hinting extensively. The `mypy` tool is used for static type checking.
*   **Commit Messages:** The project uses the `cz_gitmoji` convention for commit messages.
*   **Pre-commit Hooks:** The project uses pre-commit hooks to enforce code style and run tests before committing code. The configuration for the pre-commit hooks can be found in the `.pre-commit-config.yaml` file.
*   **Cursor Rules:** The `.cursor/rules` file contains rules for the Cursor AI code editor.

### Key Files

*   `README.md`: Provides a high-level overview of the project.
*   `justfile`: Contains a list of commands for building, testing, and running the project.
*   `pyproject.toml`: Defines the project's dependencies, scripts, and tools.
*   `src/supervaizer/cli.py`: Implements the command-line interface.
*   `src/supervaizer/server.py`: Implements the FastAPI server.
*   `src/supervaizer/agent.py`: Defines the `Agent` class, which represents an AI agent.
*   `supervaizer_control.py`: The main configuration file for your agent (created by the `scaffold` command).
*   `tests/`: Contains the project's tests.
*   `docs/`: Contains the project's documentation.

### Project Overview

The Supervaizer project is a toolkit for building and managing AI agents. It provides a framework for defining agents, their methods, and their parameters. The project also includes a web server that exposes a REST API for interacting with the agents. The API supports the A2A and ACP protocols for interoperability with other AI agent systems.

The project is built on top of several popular Python libraries, including:

*   **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
*   **Typer:** A library for building great command-line interfaces (CLIs).
*   **Pydantic:** Data validation and settings management using Python type annotations.
*   **Uvicorn:** A lightning-fast ASGI server implementation.


The project is well-structured and includes a comprehensive test suite. The documentation is also well-written and provides a good overview of the project.