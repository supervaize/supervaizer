# Persistence

> **Created:** 2025-08-06
> **Updated:** 2026-09-25

Supervaizer keeps Jobs, Cases, and server info in TinyDB through `supervaizer.storage`. Storage is **in-memory by default**; file persistence is opt-in.

## Enabling

| Setting | Effect | Default |
| --- | --- | --- |
| `SUPERVAIZER_PERSISTENCE=true` or `supervaizer start --persist` | Write to `DATA_STORAGE_PATH/entities.json` instead of memory | off |
| `DATA_STORAGE_PATH` | Directory for the JSON file | `./data` |

Both variables are read when `supervaizer.storage` is imported, so set them before importing `supervaizer`. The CLI applies `--persist` before it loads the control script. Serverless platforms with ephemeral disks should leave persistence off.

## Storage Manager

`StorageManager` is a `@singleton`: the first instantiation wins, and `supervaizer.storage` creates the module-level `storage_manager` at import time. Passing `StorageManager(db_path=...)` later in a normal process therefore has **no effect**; configure through the environment variables above. Tests get a fresh instance by clearing the singleton (see the `tests/conftest.py` fixture).

The manager stores plain dicts by table name:

```python
from supervaizer.storage import storage_manager

storage_manager.save_object("Job", job.model_dump())
storage_manager.get_objects("Job")
storage_manager.get_object_by_id("Case", case_id)      # None when missing
storage_manager.get_cases_for_job(job_id)
storage_manager.delete_object("Job", job_id)            # False when missing
storage_manager.reset_storage()
storage_manager.close()
```

`save_object` raises `ValueError` when the object has no `id`. TinyDB writes the whole file on every save (`sort_keys=True, indent=2`); there is no caching middleware.

### Tables

| Table | Written by |
| --- | --- |
| `Job` | `Job.__init__`, `add_response`, `add_case_id`, `remove_case_id` |
| `Case` | `Case.__init__` and every case update |
| `ServerInfo` | `Server` at launch when the admin interface is enabled |

`Case.job_id` and `Job.case_ids` link the two tables; `storage_manager.get_cases_for_job` follows the link.

## Typed Access

`EntityRepository[T]` wraps a table for one entity class with `get_by_id`, `save`, `get_all`, and `delete`. Use the factories `create_job_repository()` and `create_case_repository()`.

`PersistentEntityLifecycle` (`transition`, `handle_event`) applies status changes and saves the entity. `Job` and `Case` already use it internally, so application code does not need to persist entities by hand.

`Case.start(...)` is `async`; call `await Case.start(...)` or `Case.start_sync(...)`. Both send the start event to Studio through the account.

## Startup Reload

`Server.launch()` calls `load_running_entities_on_startup()`, which:

1. resets the in-memory `Jobs()` and `Cases()` registries;
2. loads jobs and cases whose status is `IN_PROGRESS`, `CANCELLING`, or `AWAITING`;
3. rebuilds them with `model_construct`, which skips validation: `status` stays a plain string and `job_context` stays a dict on reloaded entities.

`Jobs().get_job(job_id, include_persisted=True)` reads a single job from storage and rebuilds it with `Job(**data)`, which re-runs `__init__` (re-saving the job and resetting `created_at`). `Jobs().reset()` and `Cases().reset()` clear the registries.

## Security Notes

- With persistence on, decrypted `agent_parameters` are written to `entities.json` in cleartext. Protect the data directory accordingly.
- The RSA private key and server id are never written to disk. Set `SUPERVAIZER_PRIVATE_KEY` and `SUPERVAIZER_SERVER_ID` to keep them stable across restarts.

## Limitations

- Locks are process-local; do not share one `entities.json` between processes.
- Every save rewrites the whole file, which degrades with large histories.
- No migrations: the JSON is a dump of the current models.
