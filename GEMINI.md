# Gemini Instructions

Read `AGENTS.md` first. It is the canonical Supervaizer agent guide: working rules, Studio compatibility contract, learned repo facts, security rules, and GitNexus workflow.

Quick facts:

- Python 3.12+, FastAPI, Pydantic v2, Typer. Package lives in `src/supervaizer/`.
- Supervaizer is public and packaged on PyPI. Preserve API compatibility unless the task explicitly requires a breaking change.
- Use `just` recipes (`just test`, `just precommit`, `just mypy`) and `uv` for local development.
- Use GitButler (`but`) for branch, commit, and push operations when available.
- User-facing docs start at `README.md`; the v2 contract is in `docs/2026_05_SUPERVAIZER_v2.md`.
