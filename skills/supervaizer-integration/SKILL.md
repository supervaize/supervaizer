---
name: supervaizer-integration
description: Use when a user has an existing Python agent and wants to integrate it with Supervaizer v2 and Supervaize Studio, or wants to add a v2 capability to an integrated agent (Configure screen, analytics dashboards, human-in-the-loop, resources, scheduled start, rule checkpoints, guided setup, billing). This skill analyzes the agent, designs the v2 Job/Case/Step/Resource/Surface/Action mapping, then builds the controller from the SDK's own scaffold, reference docs and examples.
---

# Supervaizer Integration

Integrate an existing Python agent with Supervaizer v2. Treat v2 as the only supported target. Do not scaffold v1 job fields, `dynamic_choices`, `job_poll`, ACP, or callback-shaped UI logic.

## How To Use This Skill

This skill holds the **process** and the **design questions**. It does not hold the contract.

- Field names, document shapes, action ids, environment variables and code patterns live in the SDK, its docs and the Hello World example. **Read them every time; do not write them from memory or from this file.**
- When a reference and this skill disagree, the reference is right. Tell the user about the difference.
- Copy code from the references below, then adapt it. Do not invent a pattern that a reference already shows.

## Sources Of Truth

Use the version that matches the installed SDK. The installed package bundles its own examples. Find them with:

```bash
python -c "import supervaizer, pathlib; print(pathlib.Path(supervaizer.__file__).parent / 'examples')"
```

| Need | Source |
| --- | --- |
| Controller starting point | `supervaizer scaffold` (copies the SDK's `examples/controller_template.py`) |
| Complete small v2 agent | Installed `supervaizer/examples/hello_world_agent.py` and `local_server.py` |
| Full v2 contract | [Supervaizer v2 guide](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_SUPERVAIZER_v2.md) |
| Model fields and types | [Model reference](https://github.com/supervaize/supervaizer/tree/main/docs/model_reference) |
| Protocols and workspace authorization | [Protocols](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_PROTOCOLS.md), [Workspace agent grants](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_WORKSPACE_AGENT_GRANTS.md) |
| Install, local run, Studio connection, CLI | [SDK README](https://github.com/supervaize/supervaizer/blob/main/README.md), [Local testing](https://github.com/supervaize/supervaizer/blob/main/docs/2025_10_LOCAL_TESTING.md) |
| What each release added | [SDK changelog](https://github.com/supervaize/supervaizer/blob/main/docs/CHANGELOG.md) |
| Configure screen | [Job Configurator guide](https://docs.runwaize.com/docs/supervaizer-controller/job-configurator) |
| Dashboards | [Job and mission analytics guide](https://docs.runwaize.com/docs/supervaizer-controller/job-analytics) |
| Working agent with most capabilities, and its tests | [Hello World](https://github.com/runwaize/supervaize_hello_world) |

If the project has a local checkout of the SDK or of Hello World, read that copy.

This skill lives in the SDK repository, in `skills/supervaizer-integration/`, and is released with the SDK. Inside a checkout of the SDK, the docs are in `../../docs/` and the examples in `../../src/supervaizer/examples/`. The helper commands below use paths relative to this skill's folder.

## Core Model

Use this language consistently. The definitions are in the v2 guide, section "Core Model".

- `Job`: a user-visible unit of work started or synchronized by Studio.
- `Case`: a business item inside a Job.
- `Step`: work inside a Case.
- `Resource`: agent-owned business data Studio may manage.
- `Dataset`: agent-owned queryable analytics data.
- `Surface`: an A2UI document the agent returns for Studio to render.
- `Action`: a typed business command Studio invokes.
- `Artifact`: an agent-owned output.

## Workflow

### 1. Discover The Agent

Inspect the project before generating code:

- package manager: `pyproject.toml`, `requirements.txt`, `setup.py`
- existing web framework
- existing agent entrypoint
- environment variables and secrets
- user-facing inputs
- agent-owned data
- outputs, reports, transcripts, metrics, or files
- places where human review is required
- an existing `supervaizer_control.py` (then extend it; do not overwrite it)

Optional helper:

```bash
python scripts/supervaize_cli_helper.py analyze-agent \
  --project-root /path/to/agent \
  --pretty
```

### 2. Design The V2 Mapping

Ask only what is needed to make the v2 contract explicit:

- What is one Job?
- What are the Cases? Are they one per input item, session, contact, document, lead, or something else?
- Which lanes should Studio render?
- What Steps exist in each Case? What does each Step cost?
- Which Steps await a human, and what must the human submit?
- What Resources should Studio manage, at which scope, with which operations?
- Which dashboards should Studio render: on the mission page, on each job page, or both?
- Does a job need setup that an operator edits on the job page (a Configure screen)? Which sections, and how do they change after launch?
- What Artifacts does the agent produce?
- What external source can the agent use to converge the job status on a sync?
- Which optional capabilities below does the business ask for? Add only those.

No guessing: if workspace identity, resource scope, required secrets, or business validation rules are missing, ask or fail clearly.

### 3. Record The Mapping

Write the decisions to a spec file, so the user can review them before any code exists:

```bash
python scripts/supervaize_cli_helper.py wizard \
  --output-file integration_spec.json \
  --pretty
```

`spec-template` writes a blank spec in place of the interactive wizard. The spec is a design record. It is not a substitute for business decisions.

### 4. Install Supervaizer

Follow "Install" in the SDK README, with the target project's package manager.

### 5. Scaffold With The SDK

```bash
python scripts/supervaize_cli_helper.py scaffold-integration \
  --spec-file integration_spec.json \
  --output-dir /path/to/agent \
  --pretty
```

The helper runs the SDK's own `supervaizer scaffold`, so the controller always matches the installed SDK. It then prints a checklist built from the spec. Each item names the reference to copy from.

Work through the checklist. For each item, open the named reference, copy its pattern, and adapt it to the agent.

### 6. Smoke Test

Run the controller without Studio as the SDK README and the Local testing doc describe. Then call it:

```bash
python scripts/supervaize_cli_helper.py load-surface --help
python scripts/supervaize_cli_helper.py invoke-action --help
```

Then write tests that post the same requests to the server app. Copy the test helpers from the Hello World `tests/` folder.

### 7. Connect To Studio

Follow "Connect To Studio" in the SDK README and the Workspace agent grants doc. Tell the user that the workspace must accept the agent grant again each time the registration gains a surface or an action.

## Review Checklist

Before you report the integration as done, check each point against the named section of the v2 guide:

- Action metadata is declared, and read-only actions say so ("Action metadata").
- Every handler uses the verified workspace context for identity ("Workspace Authorization").
- Action results carry the job state where Studio reads it ("Runtime Handlers", "Core Model").
- Mutating actions are safe to retry ("Idempotency").
- The agent does not depend on Studio polling ("Sync and Offline Semantics").
- The items of "Minimal Checklist For A v2 Agent" and "Design Rules" hold.

## Optional Capabilities

Add a capability only when the mapping in step 2 calls for it. This table says when to use each one and where its contract and pattern are. It does not describe the contract.

| Capability | Use it when | Contract | Pattern to copy |
| --- | --- | --- | --- |
| Human in the loop | A step needs a person's input or approval | v2 guide, "Step" | Hello World `agent_v2.py`, `tests/test_hitl.py` |
| File upload fields | The person must send a file | v2 guide, "Step" | v2 guide |
| Resources | Studio must list or edit agent-owned data | v2 guide, "Resources" | Hello World `agent_data_resource.py` |
| Analytics dashboards | The agent has data worth charting, per job or per mission | Analytics guide | Hello World `agent_dashboard.py` |
| Artifacts and deliverables | A step produces something the user opens or exports | v2 guide, "Artifact" | Hello World `agent_deliverable.py` |
| Job Configurator | A job needs setup that an operator edits on the job page | Job Configurator guide | Hello World `agent_configurator.py`, `tests/test_configurator.py` |
| Guided setup | Studio's chat or setup panel must guide the start of a job | v2 guide, "Setup plan and field schema", "Help actions and dry runs" | v2 guide |
| Scheduled start | Studio must start the agent on a schedule | v2 guide, "Scheduled start" | Hello World `tests/test_scheduling.py` |
| Rule checkpoints | Mission rules must be able to allow, pause or stop a step | v2 guide, "Rule checkpoints" | Hello World `agent_rules.py` |
| Workspace binding | An agent-side record must be bound to a workspace before use | Workspace agent grants doc | Workspace agent grants doc |
| Context assignment | Studio must assign a frozen context selection to a job | v2 guide, "Context assignment semantics" | v2 guide |
| Labels and tooltips | Surfaces and actions need readable names in Studio | v2 guide, "Display text" | v2 guide |
| Introduction and full description | The agent needs a presentation in Studio | v2 guide, "Introduction", "Full description" | v2 guide |
| Billable consumption | The agent reports usage that the workspace pays for | v2 guide, "Billing catalog" | [Billable consumption doc](https://github.com/supervaize/supervaizer/blob/main/docs/2026_10_BILLABLE_CONSUMPTION.md) |

The SDK changelog says which release added each capability. Check it against the installed version before you use one.

## Design Guidance

These points are decisions, not contract. The guides hold the details.

**Job Configurator.** Design the sections with the user from the component catalog in the guide. Plan how the screen changes over the life of the job: before the domain object exists, during setup, while the job runs, and after it ends. The guide section "Design the screen over the life of the job" lists the cases. Always test each emitted document against the guide's refusal rules, as Hello World does.

**Analytics dashboards.** Decide first the questions the operator asks, then choose KPI cards and charts for them. One builder can serve the job and the mission. Scope a job dashboard to its job and check the workspace, as the guide says.

**Guided setup.** Ask the operator for nothing that Studio already holds. Present every agent proposal as a proposal that the user accepts. State a cost estimate as a range with its unit, or as unknown with the reason.

## Output Expectations

When completing a Supervaizer v2 integration, report:

- Job/Case/Step mapping
- lane vocabulary
- registered surfaces
- registered actions, with their declared metadata
- resource and dataset contracts
- HITL forms
- optional capabilities added, and the references they were built from
- the installed SDK version
- tenant/workspace access control assumptions
- smoke tests run
- remaining business logic TODOs
- any difference found between this skill and a reference
