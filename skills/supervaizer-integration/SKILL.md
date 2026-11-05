---
name: supervaizer-integration
description: Use when a developer wants to connect a Python agent to Supervaize Studio with the Supervaizer SDK, or wants to add a capability to a connected agent - parameters and secrets, form fields, shared resources, cost reporting, human in the loop, guardrail controls (rule checkpoints), a Configure screen, or analytics dashboards.
---

# Supervaizer Integration

Connect an existing Python agent to Supervaize Studio with the Supervaizer SDK.

Your job has two halves. First, make the developer decide what a mission, a job, a case and a step are for this agent: you ask, they decide. Second, build what they decided from the references: you read, you do not invent.

## Two Rules

1. **The contract is not in this skill.** Field names, document shapes, action ids, environment variables and code patterns live in the guides, the SDK and the Hello World example listed below. Read them each time. Do not write them from memory. When a reference and this skill disagree, the reference is right; tell the developer.
2. **Decisions belong to the developer.** Never choose the mapping for them, and never fill a gap with a guess. Ask.

## Sources Of Truth

Guides are at `https://docs.runwaize.com/docs/supervaizer-controller/<page>`. Hello World is at `https://github.com/runwaize/supervaize_hello_world`.

| Topic | Guide page | Pattern to copy in Hello World |
| --- | --- | --- |
| Missions, jobs, cases, steps | `core-concepts` | `agent_v2.py` |
| Registration, start form, field definitions, job state | `controller-setup` | `agent_v2.py`, `supervaizer_control.py` |
| Parameters and secrets | `parameters` | `supervaizer_control.py` |
| Shared resources | `resources` | `agent_data_resource.py`, `agent_v2.py` |
| Cost reporting | `cost-reporting` | `agent_v2.py` |
| Human in the loop | `human-in-the-loop` | `agent_v2.py`, `tests/test_hitl.py` |
| Guardrail controls (rule checkpoints) | `rule-checkpoints` | `agent_rules.py`, `tests/test_rule_checkpoints.py` |
| Configure screen | `job-configurator` | `agent_configurator.py`, `tests/test_configurator.py` |
| Analytics dashboards | `job-analytics` | `agent_dashboard.py` |
| First run and Studio credentials | `quickstart` | `README.md` |

Other references:

- Controller starting point: `supervaizer scaffold`.
- Full contract: [Supervaizer v2 guide](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_SUPERVAIZER_v2.md) and the [model reference](https://github.com/supervaize/supervaizer/tree/main/docs/model_reference).
- Workspace authorization: [Workspace agent grants](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_WORKSPACE_AGENT_GRANTS.md).
- Scheduled start, guided setup, billing, labels: the v2 guide sections of those names.
- What each release added: [SDK changelog](https://github.com/supervaize/supervaizer/blob/main/docs/CHANGELOG.md). Check it against the installed version.

This skill lives in the SDK repository, in `skills/supervaizer-integration/`. Inside a checkout of the SDK, the docs are in `../../docs/` and the examples in `../../src/supervaizer/examples/`. If the project has a local checkout of the SDK or of Hello World, read that copy. Helper commands below use paths relative to this skill's folder.

## The Interview

Interview the developer until every decision below is made. Treat the design as a tree: each decision opens the decisions that depend on it.

**How to ask**

- Work in rounds. A round holds every question that you can ask now, without a guess about an answer that you do not have yet.
- Number the questions. Give each one your **recommended answer** and the evidence for it from their code ("`run_batch()` loops over `leads`, so I recommend one case per lead").
- Then stop and wait. Do not write code for a branch that is still open.
- Facts are your job: read the code, the config and the tests. Do not ask the developer for something that you can look up. Decisions are their job.

**How to push**

- Do not accept "it depends" or "whatever is simpler". Ask for the last real run: what started it, how many items it had, what went wrong, who looked at the result.
- Restate each answer as a concrete example, and let them correct it: "So for Monday's run: one job, 40 cases, each case has three steps, and the second step costs money. Right?"
- Ask "what does the operator see when this fails?" for every step.
- When an answer makes the job page useless (one job with one case with one step called "run"), say so and ask again.

**During the build**

The interview does not end when the code starts. When the code shows a point that nobody decided, stop and ask a new round. Typical points: what a refusal does, what a retry of the same start does, what happens to the other cases when one fails, what survives a restart, which workspace owns a row.

### Round 1: the job

1. Which business goal do several runs of this agent serve together? That is the **mission**.
2. What does an operator start with one click, and what is finished when it is finished? That is the **job**.
3. Who starts it: a person, a schedule, or both?
4. Is the work done when `job.start` answers, or does it continue for minutes, hours or days?
5. Does the job need setup after it is created and before it works?

### Round 2: the cases

1. What does the operator count when they ask "how many are done"? That is the **case**: a contact, a document, a ticket, a lead.
2. Is the list of cases known at the start, or do cases appear while the job runs?
3. When one case fails, do the others continue?
4. What names a case on one line (its title), and what stable id does it have in the agent's own data?

### Round 3: the steps

For each activity of a case that an operator must see:

1. What is it called, in the operator's words?
2. Can it fail? What does the operator see then?
3. Does it cost money?
4. Does it produce something to open or export?
5. Does it have an effect outside the agent: a message sent, money spent, a record changed, something published or deleted?
6. Can it need a person: missing information, low confidence, a decision that someone must own?

Push back on steps that are internal function calls. A step is worth showing when it can fail, wait, cost money or produce an output.

### Round 4: what the answers opened

Ask the questions of every topic that the first three rounds opened. Ask them together.

| Topic | Bring it up when | Ask |
| --- | --- | --- |
| **Start form fields** | Always | What must the operator give to start a job? For each value: type, required or not, default, allowed choices, and which field appears only for some values of another? |
| **Parameters and secrets** | The code reads API keys, model names or other settings | Which settings are the same for all jobs of a workspace? Which are secrets? Which belong to the deployment and not to a workspace? |
| **Cost reporting** | Always | What costs money in each step (model calls, paid tools)? Where does the code know the real amount? Is an estimate needed before the start? |
| **Human in the loop** | A step has an effect that cannot be undone, can be unsure, or needs information that only a person has | Which step waits? What must the person see to decide? What do they answer? What does a refusal do? |
| **Guardrail controls** | A step has an effect outside the agent. Recommend it for each such step | Which facts of the step must a mission rule be able to judge (recipient, amount, operation)? Before the effect, after it, or both? |
| **Shared resources** | Several jobs use the same data, or operators must see or correct it | Which data? Who shares it: the workspace, a mission, a job? What may Studio do: list, create, update, delete, import? Which form must offer it as a choice? |
| **Configure screen** | Round 1 said that the job needs setup, or settings change while the job runs | Which sections? What is editable before launch, while it runs, after it ends? What must be true before launch? What is the main button? |
| **Analytics** | The agent has numbers that an operator follows. Offer a job dashboard by default | Which three numbers tell the operator that the job goes well? Which chart? Per job, per mission, or both? Which filter? |

Introduce human in the loop and guardrail controls yourself when the answers of round 3 call for them. Do not wait for the developer to ask.

### Close the interview

Summarize the whole design in one message: mission, job, cases, steps, and each topic. Ask the developer to confirm it. Build only after they confirm.

## Workflow

### 1. Read the project

Before the first question, read:

- the package manager files and the agent's entrypoint
- environment variables and secrets
- inputs, loops over items, outputs and files
- calls with outside effects
- an existing `supervaizer_control.py` (then extend it; do not overwrite it)

```bash
python scripts/supervaize_cli_helper.py analyze-agent --project-root /path/to/agent --pretty
```

### 2. Run the interview

Follow "The Interview" above.

### 3. Record the decisions

Write the confirmed design to a spec file, so the developer can review it and so the next session can read it:

```bash
python scripts/supervaize_cli_helper.py spec-template --output-file integration_spec.json --pretty
```

Fill every section of the spec from the interview. Put a decision that has no slot under `notes`.

### 4. Install and scaffold

Install the SDK as the `quickstart` guide says. Then:

```bash
python scripts/supervaize_cli_helper.py scaffold-integration \
  --spec-file integration_spec.json --output-dir /path/to/agent --pretty
```

The helper runs the SDK's `supervaizer scaffold` and prints a checklist built from the spec. Each item names its guide and its Hello World pattern.

### 5. Build one topic at a time

Build in this order. For each topic: read its guide, copy the Hello World pattern, adapt it, write a test, run it.

1. Registration, start form and job state (`controller-setup`)
2. Parameters and secrets (`parameters`)
3. Cost reporting (`cost-reporting`)
4. Human in the loop (`human-in-the-loop`)
5. Guardrail controls (`rule-checkpoints`)
6. Shared resources (`resources`)
7. Configure screen (`job-configurator`)
8. Analytics dashboards (`job-analytics`)

Skip a topic only when the developer decided against it in the interview. Say which topics you skipped and why.

### 6. Test

Run the controller without Studio and call it, as `controller-setup` shows:

```bash
python scripts/supervaize_cli_helper.py load-surface --help
python scripts/supervaize_cli_helper.py invoke-action --help
```

Write tests that post the same requests to the server app. Copy the helpers from the Hello World `tests/` folder.

### 7. Connect to Studio

Follow the `quickstart` guide and the Workspace agent grants doc. Tell the developer that a workspace admin must accept the agent grant again each time the registration gains a surface or an action.

## Review Before You Finish

Check each point against its guide:

- Every case and step has a title that an operator understands.
- The job state is returned where Studio reads it, and a repeated start does not run the work twice.
- Read-only actions are declared as read-only.
- Every handler takes the workspace from the verified context, never from the input.
- No secret reaches a result, a title, case metadata or a log.
- Every step with an outside effect has a guardrail checkpoint, or the developer declined it.
- Every Configure document passes the refusal rules of its guide.
- The checklists at the end of each guide hold.

## Report

When you finish, report:

- the mission, job, case and step mapping, as the developer confirmed it
- start form fields, parameters and secrets
- cost: what is counted, and where
- human steps and guardrail checkpoints, and the steps where the developer declined them
- resources, Configure sections and dashboards
- registered surfaces and actions
- the installed SDK version
- tests run and their result
- open decisions and business logic still to write
- any difference found between this skill and a reference
