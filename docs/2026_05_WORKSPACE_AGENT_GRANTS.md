# Workspace Agent Grants

> **Created:** 2026-05-18
> **Updated:** 2026-05-18

This document plans the Supervaizer v2 authorization model for shared agents.

The problem is not routing. A workspace slug can route a request, but it cannot prove that the workspace approved the agent. If agents accept `tenant_slug` or `workspace_slug` as authority, an agent developer could simulate Studio calls for another workspace and read or mutate agent-side data without that workspace's approval.

The recommended model is a Studio-owned **Workspace Agent Grant** plus a short-lived Studio-signed workspace authorization token on every Studio-to-agent request.

## Decision

Studio must be the source of truth for workspace approval.

When a recipient workspace admin accepts a shared agent, Studio creates a durable grant:

```text
WorkspaceAgentGrant
- id
- workspace_id
- workspace_slug
- agent_id
- server_id
- accepted_by_admin_id
- status: accepted | revoked | suspended
- scopes
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

The token should be a compact signed JWT or equivalent signed envelope.

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
  "agent_tenant_ref": "01AGENTTENANT",
  "iat": 1779100000,
  "exp": 1779100600,
  "jti": "01TOKEN"
}
```

`workspace_slug` is informational. The trusted identity is `workspace_id` plus `grant_id`.

`agent_tenant_ref` is optional but useful for stateless agents. If present, Studio owns the binding between the Studio workspace grant and the agent-side tenant reference. If absent, the agent may resolve the binding from an external data store using `grant_id` or `workspace_id`.

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

Studio may show the agent to another workspace as shareable or installable. Until an admin accepts it, the recipient workspace has no active grant.

### 3. Admin Acceptance

A recipient workspace admin accepts the agent. Studio creates `WorkspaceAgentGrant(status="accepted")` with explicit scopes and optional `agent_tenant_ref`.

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
- agent_tenant_ref
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

## Agent Interviewer Application

For `agent_interviewer`, the verified workspace context should drive tenant access.

Recommended behavior:

- campaign listing requires a valid workspace grant token
- campaign listing returns only campaigns owned by the verified agent tenant reference
- campaign listing still filters to `is_supervaize=true`
- `job.start` requires `job.start` scope
- contact import requires the campaign/contact import scope
- Supabase database or tenant selection must be derived from verified context, not from raw request slug

If the token is valid but no agent-side tenant binding exists, the agent should fail clearly:

```text
Workspace is authorized in Studio but has no agent-side tenant binding.
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
- Store status, scopes, server id, agent id, workspace id, and optional agent tenant binding.
- Expose a signing key or JWKS that agents can verify.
- Mint short-lived workspace authorization tokens for Studio-to-agent calls.
- Attach tokens to A2A calls, resource calls, dataset calls, artifact calls, `job.start`, and `job.sync`.
- Fail clearly when no accepted grant exists for the workspace and agent.
- Fail clearly when a grant is revoked, suspended, missing scope, or missing agent tenant binding.

### Agent Interviewer

- Stop trusting raw tenant or workspace slug for data access.
- Resolve Supabase tenant/database context from verified workspace grant context.
- Keep campaign filtering strict: verified tenant plus `is_supervaize=true`.
- Require explicit scopes for campaign listing, campaign start, contact import, HITL submit, datasets, and artifacts.
- Add tests for accepted grant, missing grant, wrong workspace, revoked grant, missing scope, and missing tenant binding.

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
- the agent-side tenant binding is missing

Studio should surface these failures to operators as configuration or authorization errors, not as empty tables or generic loading failures.

## Acceptance Criteria

- A shared agent cannot list resources for a workspace until a workspace admin accepts the agent.
- A forged `workspace_slug` or `tenant_slug` cannot grant access.
- A valid transport API key without a workspace grant token cannot access workspace-scoped resources.
- A valid workspace token for one workspace cannot access another workspace.
- A valid workspace token for one agent cannot access another agent.
- An agent without local persistence can still verify every request.
- Revoked grants stop authorizing requests after token expiry, and immediately for operations that use introspection.
- Studio and agent_interviewer show clear errors for missing grant, missing scope, and missing tenant binding.

