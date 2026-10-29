# Guided setup contract — SDK spec skeleton

Status: frozen. Field names and types are fixed by the approved contract
freeze in the RUNWAIZE root repo,
`docs/2026-10-28-guided-setup-contract-freeze.md` (2026-10-28). The models
live in `src/supervaizer/contracts.py` and are documented in
`2026_05_SUPERVAIZER_v2.md` (Introduction, Setup plan and field schema, Help
actions and dry runs, Idempotency).

Supervaizer-side work for the self-service campaign chat flow (see
`studio/Documentation/specifications/self_service_campaign_chat_flow.md`).
The SDK defines generic contracts only; no agent-specific vocabulary.

## Objective

An agent can declare everything Studio needs to render a chat-guided,
resumable, cost-transparent setup — without informal agreements between one
agent and Studio.

## Scope

- **Agent introduction block.** Extend agent registration with tagline,
  short "what I do" text, example goals, and optional avatar. Today only
  `name` and `description` exist (`src/supervaizer/agent.py`). Studio renders
  this in the roster and as the chat opening.
- **Typed setup schema.** Formalize what is now informal between
  agent_interviewer and Studio: `depends_on` (conditional fields),
  `{value, label}` choices, `min_rows`, plus field validation rules beyond
  `required`. Today `AgentMethodField` stops at type, choices, default, widget.
- **Typed setup plan.** Replace the untyped `plan: dict` in the v2 setup policy
  (`V2JobSetupPolicy.plan`, line 663 of `src/supervaizer/contracts.py` before
  the freeze) and the untyped `V2ActionResult.setup_plan` (line 1331 before the
  freeze) with a typed multi-step wizard model, `V2SetupPlan`. A dict is still
  accepted and passes through untouched.
- **Help actions.** A generic way for an agent to expose setup-time help
  actions (suggest, validate) that a client can call mid-setup and whose
  results map to a draft of a setup field.
- **Dry-run classification.** A declared way to mark an action as a test run,
  defined by outcome, not by storage: a dry run MAY create temporary session
  data and MAY incur model costs (which it reports), but MUST NOT send any
  external communication and MUST NOT appear in campaign results or analytics.
  Temporary data expires or is deletable.
- **Cost estimate.** An optional cost-estimate field in the preview response
  that clients render before confirm. The field expresses uncertainty: a range
  or an explicit "unknown", never a false exact number.
- **Idempotency.** Document the confirm idempotency key as part of the v2
  contract, including client retry rules after an uncertain result. Add a
  conformance test agents must pass: replaying a confirm with the same
  operation key and identities yields the same result and creates nothing new.
- **Memory write action (phase 2).** A generic action for an agent to store a
  user-scoped preference in the platform, with user visibility guaranteed by
  the client.

## Contract discipline

Update producer and consumer in the same workstream, with tests on both sides,
and update the v2 protocol docs (`2026_05_SUPERVAIZER_v2.md`).

## Compatibility

Every new field and action in this spec is optional. An agent that declares
none of them keeps its current behavior unchanged; clients fall back to the
present rendering. Verify this with a registration test using an unmodified
v2 agent.

## Open questions

- Where does scenario-like long content live in the schema: field type or
  artifact reference?

## Success criteria

1. Studio renders conditional fields and validation from the schema alone,
   with zero agent-specific code.
2. A second agent gets roster, guided setup, and dry-run for free by filling
   the contract.
