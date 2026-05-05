# Cases Batch Event — Studio Integration Guide

This document specifies the wire contract and the processing rules Studio must
follow to ingest the `agent.cases.batch` event emitted by the Supervaizer SDK.

## 1. Purpose

`agent.cases.batch` lets a Supervaizer agent ship a **collection of cases —
each with its full step (CaseNodeUpdate) history — as a single event**. It is
intended for:

- Backfilling cases produced offline or before the agent was connected to
  Studio.
- Bulk-importing cases from another system.
- Re-syncing local cases after a network interruption (the SDK keeps a
  persisted copy of cases and their steps).

It is the bulk equivalent of N × `agent.case.start` followed by `M ×
agent.case.update` per case, but folded into one HTTP request.

## 2. Producing the event (SDK side)

Producers use the high-level helper on `Account`:

```python
from supervaizer import Account, Case

account: Account = ...
cases: list[Case] = [...]   # each Case carries its own .updates history

# Async (recommended)
await account.send_cases_batch(cases)

# Sync entry point
account.send_cases_batch_sync(cases)

# Optional: pin all cases to one job_id (otherwise inferred when shared)
await account.send_cases_batch(cases, job_id="job_123")
```

Under the hood this builds a `CasesBatchEvent` and POSTs it to the standard
controller events endpoint (same as every other event):

```
POST {api_url}/w/{workspace_id}/api/v1/ctrl-events/
```

with the standard auth header `Authorization: Api-Key {api_key}`.

## 3. Wire contract

The envelope is the regular Supervaizer `Event` shape. Only the discriminator
fields and the `details` payload are batch-specific.

| Field         | Value                                                                          |
| ------------- | ------------------------------------------------------------------------------ |
| `event_type`  | `"agent.cases.batch"` (`EventType.CASES_BATCH`)                                |
| `object_type` | `"cases_batch"`                                                                |
| `source`      | `{"batch_size": <int>, "job": <job_id?>}` (key `"job"` only when known/shared) |
| `workspace`   | `<workspace_id>`                                                               |
| `details`     | `CasesBatchEventDetails` (see below)                                           |

### 3.1 `details` schema

Authoritative source: `supervaizer.contracts.CasesBatchEventDetails`.

```jsonc
{
  "job_id": "job_123",      // string | null  — present iff all cases share a job (or explicitly pinned)
  "count": 2,                // int — len(cases). Studio MUST ignore the wire value if it disagrees with len(cases).
  "cases": [
    {
      "case_id": "case_abc",
      "job_id":  "job_123",
      "case_ref": "job_123-case_abc",
      "name":    "...",
      "description": "...",
      "status":  "in_progress",      // EntityStatus value
      "total_cost": 12.5,
      "final_delivery": null,         // dict | null
      "metadata": { ... },            // free-form dict (datetimes are ISO strings)
      "updates": [
        {
          "index": 1,                 // 1-based step ordinal within the case
          "name":  "step name",
          "error": null,
          "cost":  0.0,
          "payload": { ... } ,        // arbitrary, may contain a "supervaizer_form"
          "is_final": false,
          "upsert": false,            // when true, replace an existing step at this index
          "scheduled_at": "...",      // ISO string, optional
          "scheduled_method": "...",  // optional
          "scheduled_status": "..."   // optional
        }
      ]
    }
  ]
}
```

The per-case shape mirrors `Case.registration_info` exactly, and each step
mirrors `CaseNodeUpdate.registration_info`. There is **no extra translation** —
Studio can reuse the same ingestion code paths it already runs for
`agent.case.start` and `agent.case.update`, simply applied in a loop.

### 3.2 Pydantic models exported for Studio

Studio consumers can import the contract models directly (the `contracts`
module is import-light and runtime-free):

```python
from supervaizer.contracts import (
    EventType,
    CasesBatchEventDetails,   # the `details` payload
    CaseBatchItemContract,    # one case + its steps
    CaseStepContract,         # one step
)
```

Use `CasesBatchEventDetails.model_validate(event["details"])` after
recognising `event["event_type"] == EventType.CASES_BATCH`.

## 4. Processing rules (Studio side)

Studio MUST implement the following semantics when handling
`agent.cases.batch`:

1. **Authentication / routing** — identical to all other `ctrl-events`. Reject
   the event if the API key is missing/invalid or if `workspace` does not
   match.
2. **Idempotency / upsert per case.** For every item in `details.cases`:
   - Look up the case by `(workspace_id, job_id, case_id)`.
   - If absent, create it using the same logic as `agent.case.start`
     (`name`, `description`, `status`, `metadata`).
   - If present, update the mutable fields (`status`, `total_cost`,
     `final_delivery`, `metadata`, `description`, `name`) without touching
     existing steps that are not in the batch.
3. **Step reconciliation per case.** For each item in `case.updates`:
   - Treat `index` as the canonical step ordinal (1-based).
   - If no step exists at `index`, create one (same logic as
     `agent.case.update`).
   - If a step already exists at `index`:
     - If the incoming step has `upsert: true`, **replace** the existing step's
       fields with the incoming values (mirrors the behavior of
       `Case.patch_step`).
     - Otherwise, leave the existing step untouched (the batch is treated as
       fill-only). This avoids accidental overwrites when the same batch is
       replayed.
   - Do not re-derive indexes from the array order; always honor `index` as
     sent.
4. **Final delivery.** If `final_delivery` is non-null on a case, persist it
   verbatim. Do not infer status from it — `status` is the source of truth.
5. **Atomicity.** Process the batch as a single DB transaction per workspace
   so a failure on one case rolls the whole batch back. Return HTTP 4xx with a
   per-case error report (`{"errors": [{"case_id": ..., "reason": ...}]}`) if
   validation fails. Return HTTP 200 with a summary
   (`{"created": N, "updated": M, "steps_created": K, "steps_updated": L}`) on
   success.
6. **Size guards.** Reject batches whose serialized payload exceeds the
   configured request body limit, or whose `len(cases)` exceeds a Studio-side
   maximum (suggested initial cap: **500 cases / 10 000 steps**). Return HTTP
   413 with the actual cap so the agent SDK can chunk and retry.
7. **Notifications.** After ingestion, emit the same downstream notifications
   (websocket / activity feed) Studio already emits for individual case
   start/update events, batched per case to keep the UI responsive.
8. **Ordering vs. live events.** A batch may be processed concurrently with
   live `agent.case.update` events for the same case. Because step
   reconciliation is keyed by `index` and uses upsert-or-skip, this is
   safe — but Studio should serialize writes per `(job_id, case_id)` to avoid
   lost updates.

## 5. Worked example

Request body posted by the SDK:

```json
{
  "source": { "batch_size": 2, "job": "job_42" },
  "workspace": "ws_abc",
  "event_type": "agent.cases.batch",
  "object_type": "cases_batch",
  "details": {
    "job_id": "job_42",
    "count": 2,
    "cases": [
      {
        "case_id": "c1",
        "job_id":  "job_42",
        "case_ref": "job_42-c1",
        "name": "Lead Acme",
        "description": "Outreach to Acme",
        "status": "in_progress",
        "total_cost": 0.5,
        "final_delivery": null,
        "metadata": {"company": "Acme"},
        "updates": [
          {"index": 1, "name": "queued",     "payload": {}, "cost": 0.0, "is_final": false, "upsert": false, "error": null},
          {"index": 2, "name": "called",     "payload": {"duration": 42}, "cost": 0.5, "is_final": false, "upsert": false, "error": null}
        ]
      },
      {
        "case_id": "c2",
        "job_id":  "job_42",
        "case_ref": "job_42-c2",
        "name": "Lead Globex",
        "description": "Outreach to Globex",
        "status": "completed",
        "total_cost": 1.2,
        "final_delivery": {"outcome": "interested"},
        "metadata": {},
        "updates": [
          {"index": 1, "name": "queued",  "payload": {}, "cost": 0.0, "is_final": false, "upsert": false, "error": null},
          {"index": 2, "name": "called",  "payload": {"duration": 110}, "cost": 1.2, "is_final": false, "upsert": false, "error": null},
          {"index": 3, "name": "closed",  "payload": {"outcome": "interested"}, "cost": 0.0, "is_final": true, "upsert": false, "error": null}
        ]
      }
    ]
  }
}
```

Expected Studio response on success:

```json
{
  "created": 2,
  "updated": 0,
  "steps_created": 5,
  "steps_updated": 0
}
```

## 6. Backwards compatibility

- `agent.cases.batch` is **additive**. Studio versions that do not yet handle
  it can return HTTP 400/422 with `{"detail": "unknown event_type"}` and the
  SDK will surface that as an `ApiError`. Producers MAY fall back to
  per-case events on `400/422` for graceful rollout.
- The controller contract version stays at `1.0`; this event type is exposed
  through `EventType.CASES_BATCH` and is therefore self-describing for
  schema-driven Studio consumers.
