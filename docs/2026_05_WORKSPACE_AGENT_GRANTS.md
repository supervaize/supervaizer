# Workspace Agent Grants

> **Created:** 2026-05-18
> **Updated:** 2026-05-18

This document plans the Supervaizer v2 authorization model for shared agents.

The problem is not routing. A workspace slug can route a request, but it cannot prove that the workspace approved the agent. If agents accept `tenant_slug` or `workspace_slug` as authority, an agent developer could simulate Studio calls for another workspace and read or mutate agent-side data without that workspace's approval.

The recommended model is a Studio-owned **Workspace Agent Grant** plus a short-lived Studio-signed workspace authorization token on every Studio-to-agent request.

## Decision

Studio must be the source of truth for workspace approval.

When a workspace admin accepts an agent, Studio creates a durable grant. This
applies both to recipient workspaces for shared agents and to the owner workspace
for its own agent. The owner workspace is not a runtime authorization bypass; it
must have an accepted grant with an explicit agent-side workspace binding before
Studio can operate the agent.

```text
WorkspaceAgentGrant
- id
- workspace_id
- workspace_slug
- agent_id
- server_id
- offered_by_workspace_id
- accepted_agent_version
- accepted_contract_fingerprint
- accepted_by_admin_id
- accepted_at
- revoked_by_user_id
- status: accepted | revoked | suspended
- scopes
- acceptance_snapshot
- created_at
- revoked_at
```

Every Studio-to-agent request that uses workspace data must include a signed workspace authorization token. The agent verifies this token before it trusts any workspace, tenant, resource, dataset, job, or action context.

Raw slugs are never authorization primitives.

## Trust Model

Supervaizer v2 has separate trust concerns:

| Concern | Existing or new mechanism | Purpose |
| --- | --- | --- |
| Agent to Studio authentication | `SUPERVAIZE_API_KEY` | Lets the agent call Studio APIs and send controller events. |
| Studio to agent transport authentication | `SUPERVAIZER_API_KEY` | Lets Studio call the agent controller. |
| Agent public key | existing server registration | Lets Studio encrypt sensitive payloads to the agent. |
| Workspace authorization | new Studio-signed grant token | Proves a workspace admin accepted this agent and that the request is scoped to that grant. |

The agent public key protects confidentiality. It does not prove that a workspace accepted the agent. Workspace approval requires the signed grant token.

## Signing Key Decision

Workspace authorization uses a dedicated Studio signing key family, separate from
skills artifact signing and separate from the agent public key exchanged during
server registration.

The token algorithm is **EdDSA with Ed25519 keys**. Supervaizer v2 should reject
tokens signed with any other JWT algorithm.

Studio must not duplicate cryptographic plumbing for every signing use case.
The shared implementation should provide reusable Ed25519 primitives for:

- keypair generation
- key id generation
- compact JWT signing
- public JWK generation
- JWKS payload generation

Skills artifact signing and workspace-grant signing may store keys in separate
tables and expose separate JWKS endpoints, but they should call the same shared
Ed25519 helper code. The separation is about trust domains and rotation policy,
not about duplicating signing logic.

## Stateless Agent Requirement

Agents may not have persistent local memory. The grant model must therefore be stateless from the agent's perspective.

Studio stores the grant. Studio signs a short-lived token. The agent verifies the token on every request and builds trusted request context only for that request.

The agent needs only stable trust material:

- Studio issuer URL
- Studio signing public key or JWKS URL
- expected `server_id`
- expected `agent_id` or `agent_slug`
- optional `SUPERVAIZER_API_KEY`

The agent does not need to store grants locally.

## Token Shape

The token is a compact EdDSA-signed JWT.

Recommended claims:

```json
{
  "iss": "https://studio.supervaize.com",
  "aud": "supervaizer-server:01SERVER",
  "sub": "workspace-agent-grant:01GRANT",
  "grant_id": "01GRANT",
  "workspace_id": "01WORKSPACE",
  "workspace_slug": "recipient-workspace",
  "agent_id": "01AGENT",
  "agent_slug": "agent-interviewer",
  "server_id": "01SERVER",
  "scopes": [
    "supervaizer/surface.load",
    "supervaizer/action.invoke",
    "resource.campaigns.list",
    "job.start"
  ],
  "agent_workspace_ref": "01AGENTWORKSPACE",
  "iat": 1779100000,
  "exp": 1779100600,
  "jti": "01TOKEN"
}
```

`workspace_slug` is informational. The trusted identity is `workspace_id` plus `grant_id`.

`agent_workspace_ref` is useful for stateless agents. If present, Studio owns the
binding between the Studio workspace grant and the agent-side workspace reference.
If absent, the agent may resolve the binding from an external trusted data store
using `grant_id` or `workspace_id`. Agents that cannot resolve that binding from
another trusted store must require `agent_workspace_ref` and fail clearly when it is
missing.

## Workspace Binding Registration

Agents that need an agent-side record before Studio can operate them declare a
generic `workspace_binding` block in the Supervaizer v2 registration. The block
does not name agent-specific concepts such as tenant, account, or project.

```json
{
  "workspace_binding": {
    "required": true,
    "modes": ["bind_existing", "create_and_bind"],
    "reference_label": "Agent workspace reference",
    "reference_help": "Select or create the agent-side record this Studio workspace may access.",
    "reference_placeholder": "Example: workspace-prod",
    "existing": {
      "action": "workspace_binding.options",
      "value_field": "agent_workspace_ref",
      "label_field": "display_name"
    },
    "create": {
      "surface": "workspace_binding.create",
      "action": "workspace_binding.create"
    }
  }
}
```

Supervaizer treats these as bootstrap capabilities:

- `workspace_binding.*` actions may run before the workspace grant exists.
- `workspace_binding.options` lists existing agent-side records that can be bound.
- `workspace_binding.create` creates a new agent-side record and returns the
  `agent_workspace_ref` Studio should store on the grant.
- `workspace_binding.create` surface can expose an A2UI form for collecting the
  fields needed to create the agent-side record.

These bootstrap calls still require normal Studio-to-agent transport
authentication through `SUPERVAIZER_API_KEY`. They do not require an existing
workspace authorization token because they are used to create the grant that
future tokens will represent. Every non-bootstrap surface and action remains
blocked until Studio sends a valid workspace authorization token.

## Request Transport

The preferred transport is an HTTP header:

```text
X-Supervaize-Workspace-Authorization: Bearer <signed-token>
```

For A2A JSON-RPC requests, Studio should also expose the verified workspace context inside the Supervaizer v2 request model after SDK verification. Agent handlers should receive trusted structured context instead of parsing headers directly.

The SDK should fail before handler dispatch when the token is missing, invalid, expired, wrong audience, wrong agent, wrong server, revoked by introspection, or missing required scope.

## Runtime Flow

### 1. Agent Registration

The agent developer configures normal server registration:

- `SUPERVAIZE_API_KEY` for agent-to-Studio calls
- server identity
- public key
- Supervaizer v2 registration and A2A Agent Card metadata

This does not grant workspace access to every tenant. It only makes the agent known to Studio.

### 2. Agent Sharing

Studio may show the agent to another workspace as shareable or installable. Until an authorized user accepts it, the recipient workspace has no active grant.

The target workspace UI should show the agent as **pending acceptance**, not as an installed or usable agent. Pending agents must not appear as selectable execution agents in mission/job flows.

### 3. Admin Acceptance

A workspace admin or agent-manager user accepts the agent. Studio creates
`WorkspaceAgentGrant(status="accepted")` with explicit scopes and, for agents
that require stateless workspace binding, a required `agent_workspace_ref`.

Acceptance must be explicit and auditable. Studio records:

- who accepted the agent
- when it was accepted
- which workspace accepted it
- which agent and server were accepted
- which agent version and v2 contract fingerprint were accepted
- which scopes were granted
- the acceptance terms or summary shown to the user

If the agent later changes its declared scopes, server identity, signing expectations, or contract fingerprint, Studio should require a new acceptance before enabling the expanded capability.

### 4. Studio Calls Agent

For `surface.load`, `action.invoke`, resource operations, dataset queries, `job.start`, and `job.sync`, Studio sends:

- `SUPERVAIZER_API_KEY` for transport authentication
- workspace authorization token for workspace authorization
- normal Supervaizer v2 request payload

### 5. SDK Verification

Supervaizer verifies the token and creates trusted request context:

```text
WorkspaceContext
- grant_id
- workspace_id
- workspace_slug
- agent_id
- agent_slug
- server_id
- scopes
- agent_workspace_ref
```

Handlers use this context. They must not trust raw `workspace_slug`, `tenant_slug`, or caller-provided resource filters as authorization.

## Revocation

The MVP should use short-lived tokens, ideally 5 to 15 minutes.

Revoked or suspended grants stop working when existing tokens expire. For high-risk operations, Studio or the SDK can add introspection:

- `job.start`
- resource imports
- resource mutations
- dataset exports
- sensitive artifact access

If introspection is enabled and Studio cannot confirm the grant, the request fails closed.

## Studio UI Impact

Studio must make agent sharing an explicit installation workflow in the target workspace.

### Target Workspace Agent States

Studio should distinguish at least these target-workspace states:

| State | Meaning | Studio behavior |
| --- | --- | --- |
| `available` | Agent was shared or made installable, but no target-workspace user has accepted it. | Show install/accept CTA only to workspace admins and agent managers. Do not allow mission/job use. |
| `accepted` | A workspace admin or agent manager accepted the agent. | Show as usable in mission/job flows according to scopes and permissions. |
| `revoked` | The workspace removed the agent. | Hide from normal mission/job flows. Existing jobs remain visible according to audit policy, but new calls fail. |
| `suspended` | Studio or the offering workspace disabled the grant. | Show a clear disabled state and block calls. |

### Acceptance Screen

The acceptance screen should show enough information for an admin or agent manager to make an informed decision:

- agent name and publisher
- offering workspace or owner
- controller server identity
- agent version
- Supervaizer v2 contract version
- requested scopes and their user-facing meaning
- resources and datasets the agent wants to expose
- whether the agent will access workspace-scoped data
- the agent-side workspace binding, if configured
- links to terms, documentation, and privacy/security information when available

The primary action should be explicit, for example `Accept agent for this workspace`. A normal member should see that admin approval is required, not a generic failure or empty agent page.

### Recording Acceptance

Studio should store an immutable acceptance snapshot on the grant. The snapshot should preserve what the user accepted even if the agent later changes its registration.

Minimum snapshot:

```json
{
  "agent_name": "agent_interviewer",
  "agent_slug": "agent-interviewer",
  "server_id": "01SERVER",
  "agent_version": "2.66.0",
  "supervaizer_contract_version": 2,
  "a2a_version": "0.2.6",
  "a2ui_version": "v0.8",
  "a2ui_catalog_version": "agent-interviewer.2026-05-18",
  "scopes": ["job.start", "resource.campaigns.list"],
  "resources": ["campaigns", "contacts"],
  "datasets": ["campaign_progress"],
  "accepted_by_user_id": "01USER",
  "accepted_at": "2026-05-18T11:30:00Z"
}
```

### Revocation By Removing The Agent

Removing the agent from the target workspace should revoke the `WorkspaceAgentGrant`.

Studio records:

- who removed the agent
- when it was removed
- reason, if provided
- previous grant id
- affected active jobs, if any

After revocation:

- Studio must stop minting workspace authorization tokens for the grant.
- Agent resource, dataset, artifact, `job.start`, and HITL calls must fail with a clear revoked-grant error.
- Existing jobs and cases should remain visible as historical/audit records unless product policy explicitly deletes them.
- Existing running jobs should follow the workspace revocation policy, likely `fail_in_studio` or `cancel_requested`, not silent continuation.

No fallback to a fresh grant should occur without a new explicit acceptance.

## Agent Interviewer Application

For `agent_interviewer`, the verified workspace context should drive tenant access.

Recommended behavior:

- campaign listing requires a valid workspace grant token
- campaign listing returns only campaigns owned by the verified agent workspace reference
- campaign listing still filters to `is_supervaize=true`
- `job.start` requires `job.start` scope
- contact import requires the campaign/contact import scope
- Supabase database or tenant selection must be derived from verified context, not from raw request slug

If the token is valid but no agent-side workspace binding exists, the agent should fail clearly:

```text
Workspace is authorized in Studio but has no agent-side workspace binding.
```

It should not fall back to slug matching.

## Cross-Repo Implementation Plan

### Supervaizer SDK

- Add a workspace authorization token verifier.
- Add typed request context for verified workspace grants.
- Add scope checks for A2A methods, actions, resources, datasets, artifacts, and sync.
- Add clear SDK errors for missing, expired, invalid, wrong-audience, wrong-agent, wrong-server, and missing-scope tokens.
- Add tests that prove handlers are not called when verification fails.
- Document that slugs are display and routing hints, not authorization.

### Studio

- Add `WorkspaceAgentGrant`.
- Create grants only from recipient workspace admin acceptance.
- Allow only workspace admins and agent-manager users to accept a shared agent.
- Add target-workspace UI states for available, accepted, revoked, and suspended agents.
- Add an acceptance screen that explains publisher, server identity, version, contract, scopes, resources, datasets, and data-access impact.
- Store status, scopes, server id, agent id, workspace id, accepted actor, accepted timestamp, acceptance snapshot, revocation actor, revocation timestamp, and optional agent workspace binding.
- Require re-acceptance when requested scopes or contract fingerprint expand.
- Revoke grants when the target workspace removes the agent.
- Expose a signing key or JWKS that agents can verify.
- Mint short-lived workspace authorization tokens for Studio-to-agent calls.
- Attach tokens to A2A calls, resource calls, dataset calls, artifact calls, `job.start`, and `job.sync`.
- Fail clearly when no accepted grant exists for the workspace and agent.
- Fail clearly when a grant is revoked, suspended, missing scope, or missing agent workspace binding.

### Agent Interviewer

- Stop trusting raw tenant or workspace slug for data access.
- Resolve Supabase tenant/database context from verified workspace grant context.
- Keep campaign filtering strict: verified tenant plus `is_supervaize=true`.
- Require explicit scopes for campaign listing, campaign start, contact import, HITL submit, datasets, and artifacts.
- Add tests for accepted grant, missing grant, wrong workspace, revoked grant, missing scope, and missing workspace binding.

## Failure Policy

No guessing and no implicit fallback.

The system must fail with explicit errors when:

- no workspace authorization token is provided
- the token is expired or malformed
- the token was not signed by Studio
- the token audience does not match the server
- the token agent does not match the called agent
- the token workspace has no accepted grant
- the grant is revoked or suspended
- the token lacks required scope
- the agent-side workspace binding is missing

Studio should surface these failures to operators as configuration or authorization errors, not as empty tables or generic loading failures.

## Acceptance Criteria

- A shared agent cannot list resources for a workspace until a workspace admin accepts the agent.
- A workspace admin or agent manager must explicitly accept a shared agent before it appears in mission/job flows.
- Studio records who accepted what, when, and under which contract/scopes.
- Removing an agent from a workspace revokes the grant and stops new token minting.
- A forged `workspace_slug` or `tenant_slug` cannot grant access.
- A valid transport API key without a workspace grant token cannot access workspace-scoped resources.
- A valid workspace token for one workspace cannot access another workspace.
- A valid workspace token for one agent cannot access another agent.
- An agent without local persistence can still verify every request.
- Revoked grants stop authorizing requests after token expiry, and immediately for operations that use introspection.
- Studio and agent_interviewer show clear errors for missing grant, missing scope, and missing workspace binding.
