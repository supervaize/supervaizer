---
name: supervaizer-integration
description: Use when a developer wants to connect a Python agent to Supervaize Studio with the Supervaizer SDK, or wants to add a capability to a connected agent - parameters and secrets, form fields, shared resources, cost reporting, human in the loop, guardrail controls (rule checkpoints), a Configure screen, artifacts, a scheduled start, or analytics dashboards. Use also when a developer needs a Studio account, a developer API key, a first registration, a deployment, or help with a registration that Studio refuses.
---

# Supervaizer Integration

Connect an existing Python agent to Supervaize Studio with the Supervaizer SDK.

Your job has two halves. First, make the developer decide what a mission, a job, a case and a step are for this agent: you ask, they decide. Second, build what they decided from the references: you read, you do not invent.

## Two Rules

1. **The contract is not in this skill.** Field names, document shapes, action ids, environment variables and code patterns live in the guides, the SDK and the Hello World example listed below. Read them each time. Do not write them from memory. When a reference and this skill disagree, the reference is right; tell the developer.
2. **Decisions belong to the developer.** Never choose the mapping for them, and never fill a gap with a guess. Ask.

## Integration Modes

Pick a mode at the start. It controls how much of the interview you run, not whether you follow the contract references when you write code.

| Mode | When | Interview | Build |
| --- | --- | --- | --- |
| **greenfield** | New integration, no v2 control script yet | Full rounds (below), one round at a time | After the developer confirms the summary |
| **upgrade** | The project already has `supervaizer_control.py`, v1 `AgentMethod`, or partial v2 | Skip empty rounds: run `analyze-agent`, propose mission / job / case / step mapping and open topics in **one** message with recommendations and evidence from the code | After one confirm on that blob (corrections OK; do not restart round 1 from scratch) |
| **recs-accepted** | The developer says “go with your recommendations”, “use your judgment”, or equivalent | Same as **upgrade**: one consolidated design message with numbered recommendations, then **one** confirm | Build after that single confirm |

In **upgrade** and **recs-accepted**, you still ask when the code contradicts a recommendation or when an outside effect, cost, or human step is unclear. You do not re-run round 1–4 serially when the developer has already delegated the mapping to you.

Record the confirmed design in `integration_spec.json` even in upgrade mode, so the next session can resume without another interview.

In **upgrade** and **recs-accepted**, when the controller file already exists, still run `scaffold-integration` for the checklist but **do not** pass `--force`. The helper skips `supervaizer scaffold` when the file is present and returns `scaffolded_by: "skipped (controller already exists; extend in place)"`. Extend the existing control script; never overwrite it without an explicit developer request.

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
| Cloud deployment | `deploy` | - |
| Public address for a local controller | `tunneling-setup` | - |
| Network rules between Studio and the controller | `network-security` | - |
| Errors at start or at registration | `troubleshooting` | - |

The Studio account guide is at `https://docs.runwaize.com/docs/supervaize-fleet/developer-account`.

Other references:

- Controller starting point: `supervaizer scaffold`.
- Full contract: [Supervaizer v2 guide](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_SUPERVAIZER_v2.md) and the [model reference](https://github.com/supervaize/supervaizer/tree/main/docs/model_reference).
- Workspace authorization: [Workspace agent grants](https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_WORKSPACE_AGENT_GRANTS.md).
- Scheduled start, guided setup, billing, labels: the v2 guide sections of those names.
- What each release added: [SDK changelog](https://github.com/supervaize/supervaizer/blob/main/docs/CHANGELOG.md). Check it against the installed version.

This skill lives in the SDK repository, in `skills/supervaizer-integration/`. Inside a checkout of the SDK, the docs are in `../../docs/` and the examples in `../../src/supervaizer/examples/`. If the project has a local checkout of the SDK or of Hello World, read that copy.

The helper script is in this skill's folder, not in the developer's project. Claude Code replaces `${CLAUDE_SKILL_DIR}` in the commands below with that folder. In another coding agent, replace it yourself with the absolute path of the folder that holds this `SKILL.md`.

## The Interview

Use **greenfield** mode below unless **upgrade** or **recs-accepted** applies (see Integration Modes).

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
| **Artifacts** | A step produces something to open or export | Which outputs? Who must open each one? Read the "Artifact" section of the v2 guide for the types, then ask which type each output has. |
| **Scheduled start** | Round 1 said that a schedule starts the job | Which values does a scheduled run use for the start form? What happens when the previous run is not finished? |
| **Billing catalog** | Other workspaces will pay to use the agent | What is the unit of sale? Which price does the owner set? Read the "Billing catalog" section of the v2 guide before you ask. |
| **Hosting** | Always | Where does the controller run: the developer's computer with a tunnel, or a cloud service? Who has the cloud account? Which address does Studio call? |
| **Studio account** | Always | Does the developer have a Studio account with Developer access? Which workspace receives the agent? Who is the admin that accepts the agent's workspace authorization? |

Introduce human in the loop and guardrail controls yourself when the answers of round 3 call for them. Do not wait for the developer to ask.

### Close the interview

Summarize the whole design in one message: mission, job, cases, steps, and each topic. Ask the developer to confirm it. Build only after they confirm.

## Workflow

### 1. Install the SDK

Install the SDK in the **project's** environment as the `quickstart` guide says. Do this first: the helper script and the `supervaizer` command need it. Then check the installed version against the SDK changelog.

Run CLI and helper commands with that environment on `PATH` (activate the venv) or via `uv run supervaizer …` from the project root. If the default `.venv` is broken or on a volume where `uv sync` fails, use another venv (for example `.venv-sv`) and set `UV_PROJECT_ENVIRONMENT` to its path, or call `path/to/venv/bin/supervaizer` explicitly. The helper's `scaffold-integration` looks for `supervaizer` on `PATH`, then common project venvs, then `uv run supervaizer`.

```bash
supervaizer --version
# or: uv run supervaizer --version
```

### 2. Read the project

Before the first question, read:

- the package manager files and the agent's entrypoint
- environment variables and secrets
- inputs, loops over items, outputs and files
- calls with outside effects
- an existing `supervaizer_control.py` (then extend it; do not overwrite it)

```bash
python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" analyze-agent --project-root /path/to/agent --pretty
```

### 3. Run the interview

Follow "The Interview" above.

### 4. Record the decisions

Write the confirmed design to a spec file, so the developer can review it and so the next session can read it:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" spec-template --output-file integration_spec.json --pretty
```

Fill every section of the spec from the interview. Put a decision that has no slot under `notes`. The command refuses to replace an existing spec file. Use `--force` only when the developer wants a blank one.

### 5. Scaffold

From the **agent project root**, with the project venv active or `uv` available:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" scaffold-integration \
  --spec-file integration_spec.json --output-dir /path/to/agent --pretty
```

The helper runs the SDK's `supervaizer scaffold` when the controller file is missing (or when `--force` is set and the developer chose to replace it). If the controller already exists, it prints only the checklist. Each item names its guide and its Hello World pattern. If it says the `supervaizer` command was not found, install the SDK in that project and retry with the venv on `PATH` or from that directory with `uv` installed.

### 6. Build one topic at a time

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

### 7. Test without Studio

Run the controller in local mode and call it, as `controller-setup` shows. Local mode needs no Studio account.

```bash
supervaizer start --local
python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" load-surface --help
python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" invoke-action --help
```

Both commands fail when the controller answers with a JSON-RPC error. Give `--job-id`, `--case-id` or `--step-id` only for a surface or an action of that scope. For a mission-scoped action, give none.

**`supervaizer/action.invoke` needs a `surface` field** in the JSON-RPC params (not only the action id). It must match the surface that owns the action (for example `job.start` for `job.start` / `job.start.preview`). The helper's `invoke-action` takes `--surface` (default `job.start`); copy Hello World `tests/` for in-process tests.

**Smoke checklist (running controller):**

1. `discover-controller --controller-url …` shows `/a2a`.
2. `load-surface` for the start surface returns A2UI without JSON-RPC error.
3. `invoke-action` with the correct `--surface` and `--action` (use `--dry-run` first if unsure).
4. After you add or change surfaces or actions: restart the controller, then have a workspace admin **re-accept** the workspace grant in Studio.
5. If the job uses Configure: prefer a draft start (`job.start` with empty cases / draft flow) so Studio opens Configure before run; read `job-configurator` for the pattern.

Write tests that post the same requests to the server app. Copy the helpers from the Hello World `tests/` folder.

### 8. Connect to Studio

Do this part with the developer. The account and the key are theirs. Target **production Supervaize Studio** only, as in `quickstart`, the Studio account guide, and the CLI `login` section of `docs/2025_08_CLI.md`.

**The short way: `supervaizer login`**

Use this way first. It works for a developer with no Studio account and for a developer who has one. The CLI guide of the SDK (`docs/2025_08_CLI.md`, section `login`) is the reference.

1. Run the command in the project folder:

   ```bash
   supervaizer login
   ```

2. The command prints an approval page and a short code. Give both to the developer. The developer opens the page, signs in or signs up (Google works), checks that the page shows the same code, chooses the workspace and approves. You do not open the page, and you do not approve.
3. Wait. The command ends when the developer approves. It writes the Studio credentials and the workspace authorization settings to `.env`. It prints the names of the variables, never a value.
4. Check that git ignores `.env`. Add the file to `.gitignore` if it is not there.
5. Start the controller with that file, at the public address from the Hosting question:

   ```bash
   supervaizer start --env-file .env --public-url https://<public address>
   ```

6. Read the start log. It shows the Studio page of each registered agent. Give these links to the developer. This is the first time that the developer needs Studio.
7. On that page, the developer (an admin of the workspace) sets the agent's workspace reference and accepts the workspace authorization. This is the only step in Studio. The Workspace agent grants doc says what Studio and the controller refuse until then.
8. Ask the developer to start one job from Studio. Read the controller log with them.

If the command says that this Studio does not support the login, use the manual way.

**The manual way: what only the developer does**

These steps need a person in a browser. Give the developer the list, then wait. The screens are in the Studio account guide.

1. Create a Studio account, or sign in. A new account gets its own workspace, and its creator is the admin of that workspace.
2. Get Developer access for the workspace, as the Studio account guide says. Without it, Studio refuses the registration.
3. Open the Developer page of the profile menu. Create an API key. Studio shows the key one time only.
4. On the same page, copy the environment variables that Studio generated for the workspace. There are two groups: the Studio credentials, and the workspace authorization settings. The `quickstart` guide names each variable.
5. Put the variables in the project's environment file (`.env` or `.envrc`). Make sure that git ignores this file.

**What you never do, in both ways**

- Do not ask the developer to paste the API key in the chat.
- Do not read the environment file, and do not print a variable.
- Do not create the account or the key for the developer.

**The manual way: what you do**

1. Check that the variables are present. This command prints names and URL hostnames only, never secret values. For a Studio-connected controller, add `--probe-jwks` to confirm the JWKS endpoint returns HTTP 200:

   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/supervaize_cli_helper.py" env-status --pretty --probe-jwks
   ```

2. Check that the control script reads these variables and gives them to the account object, as the scaffold does. The SDK server does not read them by itself.
3. Give the controller a public address. Studio must be able to call it. Use the answer of the Hosting question: a tunnel for a local controller (`tunneling-setup`), or a cloud service (`deploy`).
4. Start the controller with `supervaizer start`. Read the log: the registration event must succeed, and the agent must be updated from Studio.
5. Tell the developer to open the agent in the Agents list of their workspace. On the agent page, a workspace admin must accept the agent's workspace authorization. The Workspace agent grants doc says what Studio and the controller refuse until then.
6. Ask the developer to start one job from Studio. Read the controller log with them.

Tell the developer that a workspace admin must accept the workspace authorization again each time the registration gains a surface or an action.

**When Studio refuses the registration**

Read the `troubleshooting` guide first. The usual causes of a refusal with status 403 are:

- the workspace variable is not the exact workspace slug that the Developer page shows
- the owner of the API key is not a member of that workspace, or lost Developer access
- the workspace has no Developer access or no active plan

Report the status code and the request id of the log. Never report a header or a key.

### 9. Deploy

When the developer chose a cloud service, follow the `deploy` guide. Run `supervaizer deploy plan` before `supervaizer deploy up`, and show the plan to the developer. The deployed controller registers itself with Studio at its start, with the same variables.

After a deployment, do the checks of step 8 again: the registration in the log, the workspace authorization, one job from Studio.

## Review Before You Finish

Check each point against its guide:

- Every case and step has a title that an operator understands.
- The job state is returned where Studio reads it, and a repeated start does not run the work twice.
- Read-only actions are declared as read-only.
- Every handler takes the workspace from the verified context, never from the input.
- No secret reaches a result, a title, case metadata or a log.
- Every step with an outside effect has a guardrail checkpoint, or the developer declined it.
- Every Configure document passes the refusal rules of its guide.
- Git ignores the environment file, and no key is in the code, the spec file or the chat.
- The registration succeeded in the controller log, and a workspace admin accepted the workspace authorization.
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
- where the controller runs, and its public address
- the Studio state: the workspace, the result of the registration, and if the workspace authorization is accepted
- tests run and their result
- open decisions and business logic still to write
- any difference found between this skill and a reference
