# Billable consumption

> **Created:** 2026-10-30
> **Status:** Implemented in Supervaizer (ships in 1.10).
> **Studio counterpart:** `studio/Documentation/specifications/workspace_credits_billing.md`, section "Agent billable consumption (Phase 3)"

An agent can bill the work it does for a workspace. It declares its SKUs at registration and pushes consumption records to Studio. Studio prices each SKU, books accepted records against the workspace's credits, and credits the agent owner's earnings. Both parts are optional. An agent that declares no catalog and reports nothing registers byte-for-byte as before.

The SDK stays generic: it carries SKUs, units and quantities. The agent owns its vocabulary (for example `interview_minute`), and Studio owns prices, grants and the ledger.

## Billing catalog

`Agent(billing_catalog=[...])` takes `BillingCatalogItem` objects or dicts. The list travels as the `billing_catalog` key of the agent registration payload (`AgentRegistrationContract.billing_catalog`). The key is omitted when the argument is `None`. An empty list is sent as `[]`.

| Field | Type | Rule |
| --- | --- | --- |
| `sku` | `str` | 1 to 64 characters, `^[a-z0-9_]+$`, unique within the catalog |
| `unit` | `str` | 1 to 32 characters, for example `minute` or `token` |
| `description` | `str` | at most 255 characters, defaults to `""` |

The catalog carries no prices. The owner workspace sets a default price per SKU on the agent page, and may set an override per guest workspace. Studio drops an invalid catalog with a debug log and never fails the registration for it.

```python
from supervaizer import Agent, BillingCatalogItem

agent = Agent(
    name="Interviewer",
    version="1.0.0",
    supervaizer_v2_registration=registration,
    billing_catalog=[
        BillingCatalogItem(sku="interview_minute", unit="minute", description="Voice interview time"),
        {"sku": "transcript_token", "unit": "token", "description": "Transcript tokens processed"},
    ],
)
```

The built-in Hello World example defines a one-SKU catalog, `HELLO_WORLD_BILLING_CATALOG`, in `src/supervaizer/examples/hello_world_agent.py`.

## Report consumption

```python
from datetime import UTC, datetime
from decimal import Decimal

from supervaizer import BillableConsumption

receipts = account.report_consumption_sync(
    [
        BillableConsumption(
            sku="interview_minute",
            quantity=Decimal("12.50"),
            unit="minute",
            job_id=studio_job_id,
            case_id=studio_case_id,
            idempotency_key=f"{session_id}:interview_minute",
            occurred_at=datetime.now(UTC),
            description="Interview session",
        )
    ],
    agent_slug=agent.slug,
)
```

`Account.report_consumption(records, *, agent_slug, workspace_id=None)` is the async form; `report_consumption_sync` has the same arguments. Both use the shared HTTP clients of `send_event`.

- Request: `POST {api_url}/w/{workspace_id}/api/v1/billing/consumption/` with `Authorization: Api-Key <key>` and `workspace: <workspace_id>`. `workspace_id` is the workspace that runs the jobs in the batch: the guest workspace, or the owner workspace for its own jobs. It defaults to the account's workspace. The SDK sets the `workspace` header to the same value as the URL. A blank `workspace_id` raises `ValueError`.
- Body: `{"agent_slug": "<slug>", "records": [...]}` with 1 to 200 records (`ConsumptionReport`). The SDK validates the batch before it sends it, also in local mode.
- Response: `200 {"results": [...]}`, one `ConsumptionReceipt` per record, in the order sent. The methods return that list. A response with a different count or order of `idempotency_key` values raises `ValueError`.

### Record fields (`BillableConsumption`)

| Field | Type | Rule |
| --- | --- | --- |
| `sku` | `str` | a SKU of the agent's catalog, same pattern as the catalog |
| `quantity` | `Decimal` | greater than 0, finite; sent as a decimal string such as `"12.50"` |
| `unit` | `str` | 1 to 32 characters |
| `job_id` | `str` | the Studio job the record bills, not empty |
| `case_id` | `str \| None` | the Studio case, if any; sent as `null` when unset |
| `idempotency_key` | `str` | 1 to 128 characters |
| `agent_cost_usd` | `Decimal \| None` | optional hint of what the agent paid, at least 0, sent as a string; Studio does not bill it |
| `description` | `str \| None` | at most 255 characters, plain text, no personal data |
| `occurred_at` | `datetime` | timezone-aware; a naive datetime is rejected. Sent as ISO 8601 |

### Receipts (`ConsumptionReceipt`)

| `status` | Meaning | What the agent does |
| --- | --- | --- |
| `accepted` | Studio stored and booked the record. | Nothing. |
| `duplicate` | Studio received a record with the same `(agent, idempotency_key)` before, whatever its status. Nothing is booked twice. | Nothing. |
| `rejected` | Studio stored the record and booked nothing. `reason` says why. | Log it. Do not resend: a rejection is final. |

Reasons: `unknown_job`, `wrong_workspace`, `agent_mismatch`, `no_grant`, `unknown_sku`, `no_price`, `invalid_quantity`, `workspace_credits_off`. `reason` is an open string; handle unknown values like any other rejection.

### Errors

Whole-batch errors raise the httpx error, as `send_event` does:

- `403`: the API key may not act for this agent in this workspace. The key user must belong to the agent's owner workspace while the target workspace holds an accepted grant for the agent, or belong to the target workspace when the agent is its own.
- `400`: Studio could not parse the body.
- Connection errors and timeouts: the batch may or may not have reached Studio. Resend the same records with the same keys.

In local mode (`SUPERVAIZER_LOCAL_MODE=true`) no request is sent and every record comes back `accepted`.

## When to report

- Report after the work is final, for example after a session is reconciled. Do not report estimates that you correct later: Studio has no update or delete for a record.
- Report in the workspace that ran the job. A batch holds the records of one workspace.
- Batch records when convenient, up to 200 per call. A single record per call is also valid.

## Idempotency keys

- Use one key per unit of work and SKU, for example `f"{session_id}:{sku}"`. Derive it from stable ids, never from the time or a random value.
- Reuse the same key for every resend of that record. A resend after a lost response answers `duplicate` and books nothing twice.
- Never reuse a key for different work. Studio answers `duplicate` for the second record and does not book it.
- Keep a record whose transport failed (an outbox, for example) and resend it with the same key.

## Compatibility

- Every field is optional for agents. An agent without `billing_catalog` sends exactly the registration keys it sent before; `tests/test_registration_compat.py` holds the golden payloads.
- `V2ActionRequest` and the A2A routes are unchanged.
- Verification: `tests/test_billing_contracts.py`, `tests/test_report_consumption.py`, `tests/test_registration_compat.py`.
