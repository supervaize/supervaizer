# Scheduled start


> **Created:** 2026-10-11
> **Status:** Implemented in Supervaizer.
> **Studio counterpart:** `studio/Documentation/specifications/job_scheduling.md`

Studio can start a job on a schedule. The schedule, the clock, and the failure policy live in Studio. Supervaizer only declares that an agent accepts being started that way, then receives a normal `job.start`.

## Capability

On the v2 agent registration, `capabilities.scheduled_start` is an optional boolean.

| Wire value | Meaning |
| --- | --- |
| Key omitted | Agent does not allow scheduled start. This is the default, so existing registrations stay unchanged. |
| `false` | Same as omitted. Studio will not schedule the agent. |
| `true` | Studio may offer a schedule for this agent and call `job.start` when a firing is due. |

Put it on `capabilities`, next to `rule_checkpoints`. It is not an action and not a surface. The agent does not run the clock, so there is no `job.schedule` action to declare.

`build_v2_agent_registration` grows an optional `scheduled_start: bool = False`. `False` omits the key. Only `True` serializes `"scheduled_start": true`.

v1 registrations do not get this field. Studio will not schedule a v1 agent.

Every later registration carries the current value. Dropping the key, or sending `false`, is how an agent withdraws the capability. Studio then pauses existing schedules. It does not delete them, and it does not fire again until a registration sends `true` and a mission manager resumes.

## What a firing looks like

Studio calls the agent's existing `job.start` with the same input a person would have submitted. No schedule id, cron expression, timezone, or error policy is added to the action input. Agents that reject unknown keys must keep working.

Studio sets `idempotency_key` to a stable value for that occurrence. A retry of the same firing must return the original job, not start a second one. An agent that sets `scheduled_start: true` has to honor `idempotency_key` on `job.start`. Agents that already do need no new handler.

A manual start can still arrive while a scheduled job is running. Studio stops a schedule from overlapping itself. It does not lock the agent against other starts.

## What the agent does not do

- Parse cron or store a schedule.
- Decide whether a failure stops future runs. That choice is Studio's, made by the mission manager.
- Treat a scheduled start as a different action from Start now.

## When this is implemented

- Round-trip test: default registration omits `capabilities.scheduled_start`.
- Round-trip test: `scheduled_start=True` serializes `true`.
- Round-trip test: `scheduled_start=False` still omits the key.
- Add the field to the v2 protocol doc only once the serializer emits it.
