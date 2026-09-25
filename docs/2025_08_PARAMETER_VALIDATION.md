# Parameter Validation (v1 methods)

> **Created:** 2025-08-12
> **Updated:** 2026-09-25

> **Legacy.** These endpoints validate v1 `AgentMethod` fields and agent `Parameter` values on request. Supervaizer v2 agents validate inside their `job.start` surface and action handlers instead (see [2026_05_SUPERVAIZER_v2.md](2026_05_SUPERVAIZER_v2.md)).

## Two Parameter Kinds

| Kind | Class | Types | Endpoint |
| --- | --- | --- | --- |
| Agent parameters (secrets, API keys, URLs) | `Parameter` via `ParametersSetup` | always strings | `validate-agent-parameters` |
| Job fields (method inputs) | `AgentMethod.fields` | `str`, `int`, `bool`, `list`, `dict`, `float` | `validate-method-fields` |

## Endpoints

Both are `POST /api/supervaizer/agents/{agent_slug}/...`, require `X-API-Key` with write scope, and exist only when the server has a `supervisor_account` or runs in local mode. They always return HTTP 200; the `valid` flag carries the result. Job start (`POST .../jobs`) does **not** validate, so call these first if you want early feedback.

### `validate-agent-parameters`

Request:

```json
{ "encrypted_agent_parameters": "<encrypted string>" }
```

The decrypted payload must be an object `{ "PARAM_NAME": "value" }`. A JSON list is renamed to `param_0`, `param_1`, ... and fails as unknown parameters. Note that job start expects the same parameters as a list of `{ "name": ..., "value": ... }` objects, so the two endpoints currently disagree on the shape.

Response:

```json
{
  "valid": false,
  "message": "Agent parameter validation failed",
  "errors": [
    "Required parameter 'API_KEY' is missing",
    "Parameter 'MAX_RETRIES' must be a string, got int"
  ],
  "invalid_parameters": {
    "API_KEY": "Required parameter 'API_KEY' is missing",
    "MAX_RETRIES": "Parameter 'MAX_RETRIES' must be a string, got int"
  }
}
```

Other outcomes: an agent without `parameters_setup` returns `valid: true` ("Agent has no parameter setup defined"); a decryption failure returns `valid: false`; a missing `encrypted_agent_parameters` validates an empty object.

### `validate-method-fields`

Request (`method_name` defaults to `job_start`):

```json
{
  "method_name": "job_start",
  "job_fields": { "company_name": "Google", "max_results": 10, "subscribe_updates": true }
}
```

Response:

```json
{
  "valid": false,
  "message": "Method field validation failed",
  "errors": [
    "Required field 'company_name' is missing",
    "Field 'max_results' must be an integer, got str"
  ],
  "invalid_fields": {
    "company_name": "Required field 'company_name' is missing",
    "max_results": "Field 'max_results' must be an integer, got str"
  }
}
```

Type checks cover the bare Python types listed above. Fields declared with a string type label (`"str"`) or a generic (`list[str]`) are not type-checked, and `True` passes an `int` check. Unknown field names and unknown method names ("Method 'X' not found", "Agent has no methods defined") are reported as errors.

## Programmatic Use

```python
agent.parameters_setup.validate_parameters({"API_KEY": "..."})
method.validate_method_fields({"company_name": "Google"})
```

Both return the same `valid` / `errors` / `invalid_*` structure as the endpoints.
