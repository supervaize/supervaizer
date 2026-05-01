# Project Rules

## Overview

Supervaizer is the open-source controller library and FastAPI server that AI agent developers embed in their agents. It registers mapped agents with Supervaize Studio so Studio can control, observe, and operate them.

This repo is public and packaged for external users, so API compatibility, typed payloads, generated documentation, and clear tests matter more than local convenience.

## Local Glossary / Terminology

- **Controller**: The Supervaizer FastAPI service embedded with or run alongside an AI agent.
- **Studio**: The Supervaize SaaS platform that receives registration/events and operates mapped agents.
- **Mapped agent**: An agent capability exposed through Supervaizer for Studio control.
- **Registration payload**: The `server.register` payload consumed by Studio.

## Data Sensitivity Notes

- Do not log or commit API keys, server secrets, workspace tokens, or customer data.
- Preserve admin access controls such as `ADMIN_ALLOWED_IPS`.
- Keep generated docs and examples free of real credentials.

## Allowed / Forbidden Actions

### Allowed
- Add focused tests for changed behavior.
- Update generated model docs when schema or public model behavior changes.
- Coordinate compatible payload changes with Studio.

### Forbidden
- Do not break public payload/API compatibility unless the user explicitly asks for a breaking change.
- Do not introduce duplicate route registrations; OpenAPI operation IDs must stay unique.
- Do not replace existing release or documentation flows with ad hoc scripts.

## Exceptions to Org Defaults

- New and modified Python files, including tests, should use explicit type annotations and return types to keep CI mypy-clean.
- The agent registration contract with Studio takes precedence over local-only simplifications.

## Team Context

Runwaize / Supervaize platform and developer tooling.

## Language/Stack Context

Python 3.12+, FastAPI, Pydantic, pytest, uv, and Hatch.
