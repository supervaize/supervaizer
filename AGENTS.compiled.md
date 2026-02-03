# This file is maintained by oat - run `oat compile` to update. - https://github.com/alain-sv/org-agentic-toolkit

> CRITICAL: Read AGENTS.compiled.md first.

## Table of Contents

- [Traceability](#traceability)
- [Entry Point](#entry-point)
- [Usage](#usage)
- [Org Constitution](#org-constitution)
- [1. Safety & Security](#1-safety-security)
- [2. Coding practice](#2-coding-practice)
- [3. Tools](#3-tools)
- [4. Architecture & Patterns](#4-architecture-patterns)
- [5. Communication](#5-communication)
- [6. Documentation](#6-documentation)
- [Org General Context](#org-general-context)
- [About Us](#about-us)
- [Products](#products)
- [Key Platforms & Technologies](#key-platforms-technologies)
- [Project Structure](#project-structure)
- [Development Philosophy](#development-philosophy)
- [Team: founder](#team-founder)
- [Mission](#mission)
- [Skill: git](#skill-git)
- [Version Control Best Practices](#version-control-best-practices)
  - [Branching](#branching)
  - [Commits](#commits)
  - [What not to commit](#what-not-to-commit)
  - [Before pushing](#before-pushing)
  - [Pull Requests](#pull-requests)
- [Skill: test](#skill-test)
- [Testing Principles](#testing-principles)
  - [Coverage](#coverage)
  - [Test Types](#test-types)
  - [Layout and Naming](#layout-and-naming)
  - [Best Practices](#best-practices)
  - [Test Maintenance](#test-maintenance)
- [Skill: javascript/nodejs](#skill-javascriptnodejs)
- [Node.js Patterns](#nodejs-patterns)
  - [Modules](#modules)
  - [Async](#async)
  - [Best Practices](#best-practices)
- [Skill: javascript/react](#skill-javascriptreact)
- [React Patterns](#react-patterns)
  - [Components](#components)
  - [State Management](#state-management)
  - [Performance](#performance)
- [Skill: python/fastapi](#skill-pythonfastapi)
- [FastAPI Patterns](#fastapi-patterns)
  - [Routes](#routes)
  - [Async](#async)
  - [Documentation](#documentation)
- [Skill: python/pytest](#skill-pythonpytest)
- [Pytest Best Practices](#pytest-best-practices)
  - [Fixtures](#fixtures)
  - [Markers](#markers)
  - [Assertions](#assertions)
- [Skill: python/python](#skill-pythonpython)
- [Skill: python/uv](#skill-pythonuv)
- [Persona: backend-developer](#persona-backend-developer)
- [Role](#role)
- [Responsibilities](#responsibilities)
- [Workflow](#workflow)
- [Key Skills](#key-skills)
- [Persona: frontend-developer](#persona-frontend-developer)
- [Role](#role)
- [Responsibilities](#responsibilities)
- [Workflow](#workflow)
- [Key Skills](#key-skills)
- [Project Rules](#project-rules)
- [Overview](#overview)
- [Local Glossary / Terminology](#local-glossary-terminology)
- [Data Sensitivity Notes](#data-sensitivity-notes)
- [Allowed / Forbidden Actions](#allowed-forbidden-actions)
  - [Allowed](#allowed)
  - [Forbidden](#forbidden)
- [Exceptions to Org Defaults](#exceptions-to-org-defaults)
- [Team Context](#team-context)
- [Language/Stack Context](#languagestack-context)
- [Personal Memory](#personal-memory)
- [My Preferences](#my-preferences)

# Compiled Agent Instructions

## Traceability

- **Repo Root**: `.`
- **Org Root**: `..`
- **Entry Point**: `AGENTS.md`
- **Constitution Version**: 1.0.0
- **Memory Files**: constitution.md, general-context.md
- **Universal Skills**: git, test
- **Language Skills**: javascript: nodejs, react, python: fastapi, pytest, python, uv
- **Personas**: backend-developer, frontend-developer
- **Teams**: founder
- **Target Agents**: cursor
- **Project Rules**: `.agent/project.md`

---


## Entry Point
*Source: AGENTS.md*

# Agent Instructions

> CRITICAL: Read AGENTS.md first.

This project follows the organization's agentic toolkit standards.

## Usage

Reference specific personas when requesting work:
- "As a **backend-developer**, implement feature X"
- "As a **frontend-developer**, implement feature Y"
- "As a **tech-lead**, review my changes"


---

## Org Constitution
*Source: ../.agent/memory/constitution.md*

<!-- version: 1.0.0 -->

# Agentic Constitution

> **Immutable Core Rules**
> This file contains the foundational principles that all agents must follow.

## 1. Safety & Security

- Do not expose secrets or credentials
- Do not modify files outside the workspace unless explicitly authorized
- Validate inputs before processing
- Never overwrite .env files without first asking and confirming
- Handle errors explicitly, avoid silent failures
- DO NOT create fallback solutions unless explicitly requested.

## 2. Coding practice

- Before making up code, always look in the best practices for the existing best of breed method to address the problem.
- Always prefer simple solutions.
- Be explicit about the solution you will implement.
- Only make changes that are requested or you are confident are well understood and related to the change being requested.
- When fixing a bug, exhaust all options in the existing implementation before introducing a new pattern; if you do, remove the old implementation.
- After a first draft of coding, always go back for possible factorizations and simplifications.
- Follow the organization's style guide for the language/framework being used
- Write unit tests first for business logic
- Avoid duplication - check codebase for similar functionality first
- Keep files at reasonable length; refactor when they exceed 200-300 lines
- Avoid one-off scripts in source files
- When using a library, get the latest documentation (e.g. via context7 MCP)
- Do not add mock data to production functions; only in tests or test-only utilities
- Consider what other areas of the codebase might be affected by changes
- Keep lists in alphabetical order where it helps (e.g. pyproject.toml dependencies, `__all__`)
- Do not implement fallback methods unless explicitly requested
- Start with Documentation folder for implementation examples when the project has one

## 3. Tools

- Use justfiles (justfile) for project commands - prefer documented commands in justfile over direct command execution
- For Python projects, use `uv` for package management instead of pip
- Use `uv run` when executing commands with the Python environment
- Check justfile for available commands before running build, test, or deployment operations

## 4. Architecture & Patterns

- Organize code following the project's established structure
- Use appropriate architectural patterns for complex business logic
- Prefer real-time communication mechanisms over polling when available; prefer WebSockets over polling when the project has WebSocket infrastructure
- DO NOT create fallback scenarios unless explicitly instructed
- Use pytest for Python unit tests (not unittest). Use existing fixtures whenever possible
- Check memory for established patterns before introducing new ones
- Add new patterns to memory when approved

## 5. Communication

- Be concise and clear
- Explain reasoning for complex decisions
- Ask for clarification when requirements are ambiguous
- When in doubt, ask for clarification
- Be explicit about the solution you will implement

## 6. Documentation

- Each source file should begin with a comment block summarizing purpose and logic
- Update comment blocks after completing changes
- Refer to Documentation folder for examples before implementing
- Follow project-specific documentation patterns when established
- After each change, update `CHANGELOG.md`: briefly describe what changed - in the "unreleased" section, which files or areas were touched, and any specs affected; keep entries concise, enough to understand the change.


---

## Org General Context
*Source: ../.agent/memory/general-context.md*

# General Organizational Context

## About Us

Supervaize builds a unified suite for supervising, managing, and scaling AI agent workflows—from experimental pilots to enterprise-wide automation. The platform enables organizations to integrate AI agents within their business processes with confidence, making them controllable, auditable, and trustworthy.

## Products

Supervaize consists of several components:

**Supervaize Studio** - The SaaS platform for business teams to onboard, optimize, and operate AI-powered workflows - This platform is build in Django

**Supervaizer Controller** - Open source agent integration component to make AI agents controllable, auditable, and trustworthy

## Key Platforms & Technologies

- **Backend**: Django (Python 3.12), Django Rest Framework
- **Frontend**: Django templates with HTMX and Alpine.js, Bootstrap
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis as message broker
- **Cache**: Redis
- **Build Tools**: Vite for JavaScript bundling, django-vite for integration
- **Authentication**: django-allauth, dj-rest-auth with JWT
- **Package Management**: uv for Python packages
- **Testing**: pytest for Python, vitest for JavaScript

## Project Structure

The main repository contains:

- **studio/** - Supervaize Studio (Django application)

  - Main Django project for business teams to manage AI workflows
  - Uses Django templates, HTMX, Alpine.js
  - Core apps in `apps/`, business logic in `sv_core/`
  - API endpoints in `apps/api/` using DRF
  - Documentation in `Documentation/` folder

- **supervaizer/** - Supervaize Controller (Python open source toolkit)

  - Open source Python toolkit for building and managing AI agents
  - Implements Agent-to-Agent (A2A) protocol
  - Provides API for agent registration, job control, event handling, telemetry
  - Supports cloud deployment to GCP Cloud Run, AWS App Runner, DigitalOcean

- **website-v2/** - Marketing website
- **9agents/** - Various AI agent implementations and examples
- **infra/** - Infrastructure as code (Terraform)
- **n8n-supervaizer/** - n8n workflow integration

## Development Philosophy

- Simplicity over complexity - always prefer simple solutions
- Test-driven development - write unit tests first for business logic
- DRY principle - avoid code duplication, check existing codebase first
- Convention over configuration - follow Django best practices
- Security and performance optimization are priorities
- Clean, organized codebase with files kept under 200-300 lines
- Explicit solutions - be clear about implementation approach


---

## Team: founder

# Team: founder

## Mission

Manage all the projects.


---

## Skill: git
*Source: ../.agent/skills/git.md*

# Git Skills

## Version Control Best Practices

### Branching

- Use feature branches for all new work
- Keep branches small and focused
- Delete branches after merge
- Do not force-push to shared or main branches without explicit agreement; prefer rebase for local cleanup only when the project allows

### Commits

- Use Conventional Commits 1.0.0 format
- Write in imperative mood (e.g., "fix" not "fixed")
- Commit message format and emoji list may be defined in the project's DEVELOPMENT.md (or equivalent); follow that when present
- Include appropriate emoji from the project's list (e.g. in DEVELOPMENT.md) when applicable
- Format: `<emoji> <type>(<scope>): <subject>` with optional body and footer
- Be concise but descriptive; focus on substantive changes
- Do not mention CHANGELOG.md changes in commits
- NEVER commit or stage files without user confirmation
- Write clear, descriptive commit messages
- Commit frequently with logical units
- Prefer small, logical commits over large mixed ones

### What not to commit

- Do not commit commented-out code, debug print/console.log, or temporary files
- Never commit secrets, .env files, or unignored build artifacts
- Ensure .gitignore is correct for the project before adding new generated or local files

### Before pushing

- Run the project's test suite (and lint if applicable) before pushing; fix failures or get explicit approval to skip

### Pull Requests

- Keep PRs small and reviewable
- Include description of changes
- Link to related tickets
- Request appropriate reviewers


---

## Skill: test
*Source: ../.agent/skills/test.md*

# Testing Skills

## Testing Principles

### Coverage
- Aim for 80%+ code coverage on critical paths
- Focus on critical paths and edge cases
- Test error conditions and boundary behaviour

### Test Types
- Unit tests: Fast, isolated, test individual functions or small units
- Integration tests: Test component/module interactions
- E2E tests: Test complete user workflows when the project uses them

### Layout and Naming
- Follow the project's test layout (e.g. `test_*.py`, `*.test.js`, or a dedicated test directory)
- Place tests next to code or in the project's chosen test tree; do not invent a new layout

### Best Practices
- Write tests before fixing bugs when practical (TDD for business logic)
- Write unit tests first for new business logic
- Keep tests independent and repeatable; avoid order-dependent or flaky tests
- Use descriptive test names that state the scenario and expected outcome
- Prefer one logical assertion per test when practical; keep tests small and focused
- Avoid testing implementation details; test behaviour and observable outcomes
- Use existing test fixtures whenever possible; before creating new fixtures, check if they already exist
- Centralize fixtures (e.g. conftest in Python); reserve mocks for side effects outside our control (APIs, web calls)
- Avoid over-mocking; prefer fixtures over mocks
- Use pytest for Python (not unittest); avoid Django TestCase unless strictly required
- Use vitest for JavaScript unit tests
- Ensure tests assert on meaningful outcomes (DB writes, attribute changes, side-effects) rather than "method was called"
- Make tests meaningful; avoid tests for cases that cannot structurally happen or impossible scenarios
- When adding a feature or fix, add or update at least one test that would fail without the change

### Test Maintenance
- NEVER touch or change existing unit tests unless explicitly directed
- When fixing tests, DO NOT change business logic—explain the problem and ask the user to decide; make it clear whether the code or the test is broken
- Do not recommend code changes unless the test cannot be fixed
- When suggesting code changes for a failing test, add comments describing impact and side-effects; recommend additional unit tests if justified
- Check if the scenario is already covered before adding a new test
- Ensure tests assert on meaningful outcomes (database writes, attribute changes, side-effects)


---

## Skill: javascript/nodejs
*Source: .agent/skills/javascript/nodejs.md*

# Node.js Skills

## Node.js Patterns

### Modules
- Use ES modules when possible
- Keep modules focused and small
- Export only what's needed

### Async
- Prefer async/await over callbacks
- Handle errors properly
- Use Promise.all for parallel operations

### Best Practices
- Use environment variables for configuration
- Log appropriately (use structured logging)
- Handle process signals gracefully


---

## Skill: javascript/react
*Source: .agent/skills/javascript/react.md*

# React Framework Skills

## React Patterns

### Components
- Use functional components with hooks
- Keep components small and focused
- Extract reusable logic to custom hooks

### State Management
- Use useState for local state
- Use Context for shared state
- Consider Redux for complex state

### Performance
- Use React.memo for expensive components
- Use useMemo/useCallback appropriately
- Avoid unnecessary re-renders


---

## Skill: python/fastapi
*Source: .agent/skills/python/fastapi.md*

# FastAPI Framework Skills

## FastAPI Patterns

### Routes
- Use dependency injection for shared logic
- Use Pydantic models for validation
- Version APIs in path or header

### Async
- Use async/await for I/O operations
- Use background tasks for long operations
- Be careful with database connections

### Documentation
- FastAPI auto-generates OpenAPI docs
- Add descriptions to routes and models
- Include examples in schemas


---

## Skill: python/pytest
*Source: ../.agent/skills/python/pytest.md*

# Pytest Testing Skills

## Pytest Best Practices

### Fixtures
- Use fixtures for test setup/teardown
- Share fixtures via conftest.py
- Use scope appropriately (function, class, module, session)

### Markers
- Use markers to categorize tests
- Use parametrize for data-driven tests
- Use skip/xfail for conditional tests

### Assertions
- Use pytest's assertion introspection
- Write descriptive assertion messages
- Use pytest.raises for exception testing


---

## Skill: python/python
*Source: ../.agent/skills/python/python.md*



---

## Skill: python/uv
*Source: ../.agent/skills/python/uv.md*


# Package Management with `uv`

These rules define strict guidelines for managing Python dependencies in this project using the `uv` dependency manager.

**✅ Use `uv` exclusively**

- All Python dependencies **must be installed, synchronized, and locked** using `uv`.
- Never use `pip`, `pip-tools`, or `poetry` directly for dependency management.

**🔁 Managing Dependencies**

Always use these commands:

```bash
# Add or upgrade dependencies
uv add <package>

# Remove dependencies
uv remove <package>

# Reinstall all dependencies from lock file
uv sync
```

**🔁 Scripts**

```bash
# Run script with proper dependencies
uv run script.py
```

You can edit inline-metadata manually:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "torch",
#     "torchvision",
#     "opencv-python",
#     "numpy",
#     "matplotlib",
#     "Pillow",
#     "timm",
# ]
# ///

print("some python code")
```

Or using uv cli:

```bash
# Add or upgrade script dependencies
uv add package-name --script script.py

# Remove script dependencies
uv remove package-name --script script.py

# Reinstall all script dependencies from lock file
uv sync --script script.py
```


---

## Persona: backend-developer
*Source: ../.agent/personas/backend-developer.md*

# Backend Developer

## Role

Specialized persona for backend development: APIs, services, database logic.

## Responsibilities

- Design and implement REST/GraphQL APIs
- Write database models and migrations
- Implement business logic and services
- Write unit and integration tests
- Ensure API security and performance

## Workflow

1. Understand requirements from tickets/user stories
2. Design API endpoints and data models
3. Implement features following org standards
4. Write comprehensive tests
5. Create/update API documentation
6. Submit PR for review

## Key Skills

- API design (REST, GraphQL)
- Database design and optimization
- Authentication and authorization
- Error handling and logging
- Performance optimization


---

## Persona: frontend-developer
*Source: ../.agent/personas/frontend-developer.md*

# Frontend Developer

## Role

Specialized persona for frontend development: UI components, pages, client logic.

## Responsibilities

- Build responsive UI components
- Implement user interactions
- Integrate with backend APIs
- Ensure accessibility (WCAG 2.1 AA)
- Optimize for performance

## Workflow

1. Understand design requirements
2. Break down into components
3. Implement components with tests
4. Integrate with APIs
5. Test across browsers/devices
6. Submit PR for review

## Key Skills

- Component architecture
- State management
- CSS/styling (responsive design)
- Accessibility
- Performance optimization


---

## Project Rules
*Source: .agent/project.md*

# Project Rules

## Overview

[1-2 paragraphs describing the project]

## Local Glossary / Terminology

- **Term 1**: Definition
- **Term 2**: Definition

## Data Sensitivity Notes

[Any data sensitivity or security considerations]

## Allowed / Forbidden Actions

### Allowed
- Action 1
- Action 2

### Forbidden
- Action 1 (with rationale)
- Action 2 (with rationale)

## Exceptions to Org Defaults

[Any exceptions to org defaults with explicit rationale and ticket reference]

## Team Context

[Which team owns this project]

## Language/Stack Context

[Which languages/frameworks are used, if not fully declared in inherits.yaml]


---

## Personal Memory

# Personal Context

Hi! I am the human user.

## My Preferences

- I prefer concise answers
- I like comments in code
- I use VS Code / Cursor / Windsurf


---
