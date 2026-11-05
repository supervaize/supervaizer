# Supervaizer Integration Skill

A skill for coding agents (Claude Code, Cursor, Codex, Gemini CLI). It integrates an existing Python agent with Supervaizer v2 and Supervaize Studio.

The skill holds the integration process and the design questions. For the contract and the code patterns it points to this SDK: `supervaizer scaffold`, the docs in [`docs/`](../../docs/), the bundled examples in [`src/supervaizer/examples/`](../../src/supervaizer/examples/), the Studio guides and the Hello World example. It is released with the SDK, so it stays in step with it.

## Install

In Claude Code:

```
/plugin marketplace add supervaize/supervaizer
/plugin install supervaizer-integration
```

Or point your coding agent to [`SKILL.md`](./SKILL.md) in a checkout of this repository.

## Helper

`scripts/supervaize_cli_helper.py` analyzes an agent project, records the mapping in a spec file, runs `supervaizer scaffold`, and calls a running controller for smoke tests. It needs only `typer`, which the SDK installs.

```bash
python scripts/supervaize_cli_helper.py --help
```
