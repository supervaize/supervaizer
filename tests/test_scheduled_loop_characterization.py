# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize local scheduled-step polling and case scheduling behavior."""

import asyncio
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from supervaizer import Account, Case, CaseNodeUpdate, EntityStatus, Job, JobContext
from supervaizer.case import Cases
from supervaizer.job import Jobs
from supervaizer.scheduled_steps import _run_scheduled_step_loop
from supervaizer.server import Server
from supervaizer.storage import StorageManager


@dataclass
class _ScheduledAgent:
    """Minimal agent shape used by the scheduled-loop boundary."""

    name: str
    allowed_methods: set[str]

    def _declared_method_paths(self) -> set[str]:
        """Return the agent method allow-list."""
        return self.allowed_methods


@dataclass
class _ScheduledServer:
    """Minimal server shape used by the scheduled-loop boundary."""

    agents: list[_ScheduledAgent]


@pytest.fixture
def isolated_scheduled_state(storage_manager: StorageManager) -> Iterator[None]:
    """Reset real singleton registries and storage for each characterization."""
    del storage_manager
    Jobs().reset()
    Cases().reset()
    yield
    Jobs().reset()
    Cases().reset()


def _new_job(job_id: str, agent_name: str) -> Job:
    """Create a real in-memory job with a stable owner agent."""
    return Job.new(
        job_context=JobContext(
            workspace_id="workspace",
            job_id=job_id,
            started_by="tester",
            started_at=datetime.now(UTC),
            mission_id="mission",
            mission_name="Mission",
        ),
        agent_name=agent_name,
    )


def _new_case(account: Account, job_id: str, case_id: str = "scheduled-case") -> Case:
    """Create a real registered case with one scheduled update slot."""
    return Case(
        id=case_id,
        job_id=job_id,
        account=account,
        status=EntityStatus.IN_PROGRESS,
        name="Scheduled case",
        description="A scheduled case",
    )


def _due_update(
    *,
    method: str | None = "agent.run",
    params: dict[str, Any] | None = None,
    status: str | None = "pending",
) -> CaseNodeUpdate:
    """Build a pending update that is due immediately."""
    return CaseNodeUpdate(
        name="Scheduled step",
        scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
        scheduled_method=method,
        scheduled_params=params,
        scheduled_status=status,
    )


def _server_for(agent_name: str, allowed_methods: set[str]) -> _ScheduledServer:
    """Create a server boundary with one declared agent."""
    return _ScheduledServer([_ScheduledAgent(agent_name, allowed_methods)])


def _as_server(server: _ScheduledServer) -> Server:
    """Cast the minimal runtime boundary to the loop's server contract."""
    return cast(Server, server)


def _cancel_after_iterations(
    iterations: int = 1,
) -> tuple[Callable[[float], Any], list[float]]:
    """Return a sleep coroutine that stops polling after the given passes."""
    sleep_calls: list[float] = []

    async def sleep_once_then_cancel(delay: float) -> None:
        sleep_calls.append(delay)
        if len(sleep_calls) == iterations + 1:
            raise asyncio.CancelledError

    return sleep_once_then_cancel, sleep_calls


def test_cases_returns_only_pending_due_scheduled_steps(
    isolated_scheduled_state: None, account_fixture: Account
) -> None:
    """Only pending updates at or before the current UTC time are due."""
    del isolated_scheduled_state
    case = _new_case(account_fixture, "due-job")
    due = _due_update()
    case.updates = [
        due,
        CaseNodeUpdate(
            name="Future step",
            scheduled_at=datetime.now(UTC) + timedelta(seconds=1),
            scheduled_status="pending",
        ),
        CaseNodeUpdate(
            name="Completed step",
            scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
            scheduled_status="completed",
        ),
        CaseNodeUpdate(name="Ordinary step"),
    ]

    assert Cases().get_due_scheduled_steps() == [(case, 0, due)]


def test_cancel_scheduled_steps_cancels_each_pending_scheduled_update(
    isolated_scheduled_state: None, account_fixture: Account
) -> None:
    """Cancellation affects pending scheduled updates, regardless of due time."""
    del isolated_scheduled_state
    case = _new_case(account_fixture, "cancel-job")
    due = _due_update()
    future = CaseNodeUpdate(
        name="Future step",
        scheduled_at=datetime.now(UTC) + timedelta(hours=1),
        scheduled_status="pending",
    )
    executing = _due_update(status="executing")
    unscheduled = CaseNodeUpdate(name="Ordinary step", scheduled_status="pending")
    case.updates = [due, future, executing, unscheduled]

    case.cancel_scheduled_steps()

    assert due.scheduled_status == "cancelled"
    assert future.scheduled_status == "cancelled"
    assert executing.scheduled_status == "executing"
    assert unscheduled.scheduled_status == "pending"


@pytest.mark.asyncio
async def test_scheduled_loop_completes_owned_allowed_step_with_default_params(
    isolated_scheduled_state: None,
    account_fixture: Account,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loop passes an empty parameter map to the owning agent allow-list."""
    del isolated_scheduled_state
    job = _new_job("allowed-job", "owner-agent")
    case = _new_case(account_fixture, job.id)
    job.add_case_id(case.id)
    update = _due_update(method="owner.run")
    case.updates = [update]
    calls: list[tuple[str, dict[str, Any], set[str] | None]] = []

    def execute(
        method: str, params: dict[str, Any], allowed_methods: set[str] | None
    ) -> None:
        calls.append((method, params, allowed_methods))

    sleep, sleep_calls = _cancel_after_iterations()
    monkeypatch.setattr("supervaizer.scheduled_steps.asyncio.sleep", sleep)
    monkeypatch.setattr(
        "supervaizer.scheduled_steps._execute_scheduled_method", execute
    )

    with pytest.raises(asyncio.CancelledError):
        await _run_scheduled_step_loop(
            _as_server(_server_for("owner-agent", {"owner.run"}))
        )

    assert sleep_calls == [60, 60]
    assert calls == [("owner.run", {}, {"owner.run"})]
    assert update.scheduled_status == "completed"


@pytest.mark.asyncio
async def test_scheduled_loop_skips_a_due_step_without_a_method(
    isolated_scheduled_state: None,
    account_fixture: Account,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A due update without a method remains pending and never executes."""
    del isolated_scheduled_state
    job = _new_job("missing-method-job", "owner-agent")
    case = _new_case(account_fixture, job.id)
    job.add_case_id(case.id)
    update = _due_update(method=None)
    case.updates = [update]
    sleep, _sleep_calls = _cancel_after_iterations()
    monkeypatch.setattr("supervaizer.scheduled_steps.asyncio.sleep", sleep)

    def should_not_execute(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("A missing scheduled method must not execute")

    monkeypatch.setattr(
        "supervaizer.scheduled_steps._execute_scheduled_method", should_not_execute
    )

    with pytest.raises(asyncio.CancelledError):
        await _run_scheduled_step_loop(_as_server(_server_for("owner-agent", set())))

    assert update.scheduled_status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("ambiguous", [False, True])
async def test_scheduled_loop_fails_orphaned_or_ambiguous_job_ownership(
    isolated_scheduled_state: None,
    account_fixture: Account,
    monkeypatch: pytest.MonkeyPatch,
    ambiguous: bool,
) -> None:
    """A step fails when no single registered job owns its case."""
    del isolated_scheduled_state
    job_id = "ambiguous-job" if ambiguous else "orphan-job"
    case = _new_case(account_fixture, job_id)
    update = _due_update(method="owner.run")
    case.updates = [update]
    if ambiguous:
        first_job = _new_job(job_id, "first-agent")
        second_job = _new_job(job_id, "second-agent")
        first_job.add_case_id(case.id)
        second_job.add_case_id(case.id)
    sleep, _sleep_calls = _cancel_after_iterations()
    monkeypatch.setattr("supervaizer.scheduled_steps.asyncio.sleep", sleep)

    def should_not_execute(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("An unresolved job must not execute")

    monkeypatch.setattr(
        "supervaizer.scheduled_steps._execute_scheduled_method", should_not_execute
    )

    with pytest.raises(asyncio.CancelledError):
        await _run_scheduled_step_loop(
            _as_server(_server_for("owner-agent", {"owner.run"}))
        )

    assert update.scheduled_status == "failed"


@pytest.mark.asyncio
async def test_scheduled_loop_marks_a_step_failed_when_execution_raises(
    isolated_scheduled_state: None,
    account_fixture: Account,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An execution exception becomes a failed scheduled-step state."""
    del isolated_scheduled_state
    job = _new_job("failed-step-job", "owner-agent")
    case = _new_case(account_fixture, job.id)
    job.add_case_id(case.id)
    update = _due_update(method="owner.run", params={"value": "input"})
    case.updates = [update]
    sleep, _sleep_calls = _cancel_after_iterations()
    monkeypatch.setattr("supervaizer.scheduled_steps.asyncio.sleep", sleep)

    def fail_execute(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("execution failed")

    monkeypatch.setattr(
        "supervaizer.scheduled_steps._execute_scheduled_method", fail_execute
    )

    with pytest.raises(asyncio.CancelledError):
        await _run_scheduled_step_loop(
            _as_server(_server_for("owner-agent", {"owner.run"}))
        )

    assert update.scheduled_status == "failed"


@pytest.mark.asyncio
async def test_scheduled_loop_recovers_after_a_polling_error(
    isolated_scheduled_state: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A polling error does not stop the next loop iteration."""
    del isolated_scheduled_state
    calls = 0

    def get_due_steps_after_one_error() -> list[tuple[Any, ...]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary storage error")
        return []

    sleep, sleep_calls = _cancel_after_iterations(iterations=2)
    monkeypatch.setattr(
        Cases(), "get_due_scheduled_steps", get_due_steps_after_one_error
    )
    monkeypatch.setattr("supervaizer.scheduled_steps.asyncio.sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await _run_scheduled_step_loop(_as_server(_server_for("owner-agent", set())))

    assert calls == 2
    assert sleep_calls == [60, 60, 60]
