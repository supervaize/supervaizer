# RFC-002: Async HTTP Client for `account_service.send_event`

**Status:** Proposed  
**Date:** 2026-04-27  
**Affects:** `supervaizer` SDK (published PyPI package)

---

## Problem

Every call from an agent to the Supervaize Control API — reporting a step, starting or closing a case — goes through `account_service.send_event()`, which issues a synchronous `httpx.Client.post()`. This is a blocking network call.

For agents built on Python's asyncio (FastAPI, Pipecat, etc.), any synchronous blocking call made from within the event loop freezes the entire server for the duration of that call. All concurrent tasks are suspended until it returns.

The SDK's `async def` hooks give the appearance of being async-safe, but they contain no real `await` points. Any agent that calls them from an asyncio context — directly or as a background task — blocks the event loop.

### Call chain (current)

```
Account.send_update_case()     # sync
  account_service.send_event() # sync
    httpx.Client.post()        # ← BLOCKS the event loop
```

`Case.update()`, `Account.send_start_case()`, and `Account.send_register_agent()` all follow the same path.

### Consequences for async agents

An agent that calls `report_step()` or `close_case()` from an asyncio background task — even fire-and-forget — blocks the event loop for the full duration of the HTTP round-trip. Observed latencies range from 2s (fast network) to 34s (slow or retried requests). During that window the agent's audio pipeline, WebSocket transport, and all other async work is frozen.

The only workaround available to consumers is to wrap every SDK call in `asyncio.to_thread(...)`, which is error-prone, requires duplicating logic, and must be applied at every call site across the agent's lifecycle.

---

## Proposed Change

Make `account_service.send_event()` async and replace `httpx.Client` with `httpx.AsyncClient`. Cascade the `async`/`await` change up through all SDK methods that call it.

This is a **minor breaking change** for callers that invoke SDK methods from synchronous code (CLI tools, scripts). A sync shim covers those cases — see Backward Compatibility.

### `account_service.py`

**Before:**
```python
_httpx_transport = httpx.HTTPTransport(retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2)))
_httpx_client = httpx.Client(transport=_httpx_transport)

def send_event(account, sender, event) -> ApiResult:
    ...
    response = _httpx_client.post(url_event, headers=headers, json=payload)
    response.raise_for_status()
    ...
```

**After:**
```python
_httpx_transport = httpx.AsyncHTTPTransport(retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2)))
_httpx_client = httpx.AsyncClient(transport=_httpx_transport)

async def send_event(account, sender, event) -> ApiResult:
    ...
    response = await _httpx_client.post(url_event, headers=headers, json=payload)
    response.raise_for_status()
    ...
```

`httpx.AsyncClient` must remain a module-level singleton to reuse the connection pool. It must be closed gracefully on server shutdown (via a lifespan handler or `atexit`).

### `account.py` — cascade

```python
async def send_update_case(self, case, update) -> ApiResult:
    from supervaizer.event import CaseUpdateEvent
    event = CaseUpdateEvent(case=case, update=update, account=self)
    return await account_service.send_event(update, event)

async def send_start_case(self, case) -> ApiResult:
    from supervaizer.event import CaseStartEvent
    event = CaseStartEvent(case=case, account=self)
    return await account_service.send_event(case, event)

async def send_register_agent(self, agent, polling) -> ApiResult:
    from supervaizer.event import AgentRegisterEvent
    event = AgentRegisterEvent(agent=agent, account=self, polling=polling)
    return await account_service.send_event(agent, event)
```

### `case.py`

`Case.update()` currently calls `self.account.send_update_case(self, ...)` synchronously:

```python
async def update(self, update: CaseNodeUpdate) -> ApiResult:
    return await self.account.send_update_case(self, update)
```

---

## Backward Compatibility

Callers that invoke SDK methods from synchronous code (CLI registration, telemetry scripts) will break if they call the async methods directly. Provide a sync shim in `account_service.py`:

```python
def send_event_sync(account, sender, event) -> ApiResult:
    """Sync entry point for environments without a running event loop (CLI, scripts)."""
    import asyncio
    try:
        asyncio.get_running_loop()
        # Already inside a loop — run in a thread to avoid deadlock
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, send_event(account, sender, event)).result()
    except RuntimeError:
        return asyncio.run(send_event(account, sender, event))
```

All existing sync callers (CLI, `send_telemetry`) switch to `send_event_sync`. Async agent callers use `await send_event(...)`.

---

## What Does NOT Change

- The public API contract to the Supervaize Control API (URL, headers, payload shape) is unchanged.
- The outbox retry path runs from a scheduled background job, not from the agent hot path, and can remain sync.
- Error handling, retry configuration (`SUPERVAIZE_HTTP_MAX_RETRIES`), and local-mode short-circuit logic are unchanged.

---

## Acceptance Criteria

1. `account_service.send_event` is `async def` and uses `httpx.AsyncClient`.
2. `Account.send_update_case`, `send_start_case`, `send_register_agent` are `async def`.
3. `Case.update()` is `async def`.
4. `account_service.send_event_sync` provides a safe sync entry point for CLI and script callers.
5. All existing SDK tests pass without modification.
6. New tests verify that `send_event` can be `await`-ed from an async test without blocking.
7. The SDK example agents (FastAPI, Pipecat) register and report steps correctly after the change.
 