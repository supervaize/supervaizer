# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize the local Hello World agent job workflow."""

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from supervaizer.case import Case, CaseNodeUpdate, Cases
from supervaizer.examples.hello_world_agent import _job_id_from_params, job_start
from supervaizer.job import Job, JobContext, Jobs
from supervaizer.lifecycle import EntityStatus
from supervaizer.storage import StorageManager


@pytest.fixture
def isolated_job_registries(storage_manager: StorageManager) -> Iterator[None]:
    """Keep the singleton registries and backing store isolated per test."""
    del storage_manager
    Jobs().reset()
    Cases().reset()
    yield
    Jobs().reset()
    Cases().reset()


@pytest.fixture
def deterministic_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove simulated step delays and random duration values."""
    monkeypatch.setattr(
        "supervaizer.examples.hello_world_agent.random.uniform",
        lambda _lower, _upper: 1.25,
    )
    monkeypatch.setattr("supervaizer.examples.hello_world_agent.time.sleep", _no_sleep)


def _no_sleep(_duration: float) -> None:
    """Replace the simulated delay used by the local example."""


def _new_job(job_id: str) -> Job:
    """Create a real in-memory job accepted by the example handler."""
    return Job.new(
        job_context=JobContext(
            workspace_id="test-workspace",
            job_id=job_id,
            started_by="test-user",
            started_at=datetime.now(UTC),
            mission_id="test-mission",
            mission_name="Test mission",
        ),
        agent_name="hello-world-test",
    )


def _only_case(job_id: str) -> Case:
    """Return the single case created for a one-case job."""
    cases = list(Cases().get_job_cases(job_id).values())
    assert len(cases) == 1
    return cases[0]


@pytest.mark.parametrize(
    ("params", "expected_job_id"),
    [
        ({}, "local-job"),
        ({"context": SimpleNamespace(job_id="object-job")}, "object-job"),
        ({"context": {"job_id": "dict-job"}}, "dict-job"),
        ({"context": {}}, "local-job"),
    ],
)
def test_job_id_from_params_uses_context_when_available(
    params: dict[str, Any], expected_job_id: str
) -> None:
    """The local handler uses object and dictionary job context forms."""
    assert _job_id_from_params(params) == expected_job_id


def test_job_start_defaults_to_one_case_when_count_is_empty(
    isolated_job_registries: None, deterministic_steps: None
) -> None:
    """An omitted count produces one completed case with all normal updates."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("default-count-job")

    response = job_start(context=job.job_context, fields={})

    case = _only_case(job.id)
    assert response.status == EntityStatus.COMPLETED
    assert response.message == "Completed 1 cases"
    assert job.case_ids == [case.id]
    assert [update.name for update in case.updates] == ["Begin", "Progress", "End"]
    assert [
        update.payload["duration"]
        for update in case.updates
        if update.payload is not None
    ] == [1.25, 1.25, 1.25]
    assert case.final_delivery == {"result": "Case 1 completed"}
    assert case.status == EntityStatus.COMPLETED


def test_job_start_clamps_a_negative_count_to_zero(
    isolated_job_registries: None, deterministic_steps: None
) -> None:
    """A negative count completes without creating cases."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("negative-count-job")

    response = job_start(
        context=job.job_context,
        fields={"How many times to say hello": -4},
    )

    assert response.status == EntityStatus.COMPLETED
    assert response.message == "Completed 0 cases"
    assert job.case_ids == []
    assert Cases().get_job_cases(job.id) == {}


def test_job_start_clamps_a_large_count_to_one_hundred(
    isolated_job_registries: None, deterministic_steps: None
) -> None:
    """A large count creates no more than one hundred cases."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("maximum-count-job")

    response = job_start(
        context=job.job_context,
        fields={"How many times to say hello": 101},
    )

    cases = list(Cases().get_job_cases(job.id).values())
    assert response.status == EntityStatus.COMPLETED
    assert response.message == "Completed 100 cases"
    assert len(job.case_ids) == 100
    assert len(cases) == 100
    assert all(len(case.updates) == 3 for case in cases)
    assert all(case.status == EntityStatus.COMPLETED for case in cases)


def test_job_start_rejects_a_non_numeric_count(isolated_job_registries: None) -> None:
    """A count that cannot convert to an integer raises before case creation."""
    del isolated_job_registries
    job = _new_job("invalid-count-job")

    with pytest.raises(ValueError, match="invalid literal for int"):
        job_start(
            context=job.job_context,
            fields={"How many times to say hello": "many"},
        )

    assert Cases().get_job_cases(job.id) == {}


def test_job_start_stops_before_creating_a_case(
    isolated_job_registries: None, deterministic_steps: None
) -> None:
    """A stopped job returns a stopped response without making a case."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("stopped-before-case-job")
    job.status = EntityStatus.STOPPED

    response = job_start(context=job.job_context, fields={})

    assert response.status == EntityStatus.STOPPED
    assert response.message == "Stopped after 0/1 cases"
    assert job.case_ids == []
    assert Cases().get_job_cases(job.id) == {}


def test_job_start_stops_during_a_case_after_the_current_update(
    isolated_job_registries: None,
    deterministic_steps: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stopping during a case leaves its completed update but skips closing it."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("stopped-during-case-job")
    original_update_sync = Case.update_sync

    def stop_after_first_update(
        case: Case, update: CaseNodeUpdate, **kwargs: Any
    ) -> None:
        original_update_sync(case, update, **kwargs)
        job.status = EntityStatus.STOPPED

    monkeypatch.setattr(Case, "update_sync", stop_after_first_update)

    response = job_start(context=job.job_context, fields={})

    case = _only_case(job.id)
    assert response.status == EntityStatus.STOPPED
    assert response.message == "Stopped after 0/1 cases"
    assert [update.name for update in case.updates] == ["Begin"]
    assert case.final_delivery is None
    assert case.status == EntityStatus.IN_PROGRESS


def test_job_start_stops_while_waiting_for_human_review(
    isolated_job_registries: None,
    deterministic_steps: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job stopped during review leaves the case awaiting input."""
    del isolated_job_registries, deterministic_steps
    job = _new_job("stopped-while-awaiting-job")
    sleep_calls: list[float] = []

    def stop_while_awaiting(duration: float) -> None:
        sleep_calls.append(duration)
        if duration != 1.0:
            return
        case = _only_case(job.id)
        assert case.status == EntityStatus.AWAITING
        job.status = EntityStatus.STOPPED

    monkeypatch.setattr(
        "supervaizer.examples.hello_world_agent.time.sleep", stop_while_awaiting
    )

    response = job_start(
        context=job.job_context,
        fields={"Enable human review": True},
    )

    case = _only_case(job.id)
    assert response.status == EntityStatus.STOPPED
    assert response.message == "Stopped after 0/1 cases"
    assert sleep_calls == [1.25, 1.25, 1.0]
    assert case.status == EntityStatus.AWAITING
    assert [update.name for update in case.updates] == [
        "Begin",
        "Progress",
        "Human Review",
    ]
    assert case.updates[-1].payload is not None
    assert "supervaizer_form" in case.updates[-1].payload


@pytest.mark.parametrize("approved", [True, False])
def test_job_start_continues_after_any_human_review_answer(
    isolated_job_registries: None,
    deterministic_steps: None,
    monkeypatch: pytest.MonkeyPatch,
    approved: bool,
) -> None:
    """Both approved and rejected review answers resume and complete the case."""
    del isolated_job_registries, deterministic_steps
    job = _new_job(f"review-answer-{approved}-job")

    def answer_human_review(_duration: float) -> None:
        case = _only_case(job.id)
        if case.status == EntityStatus.AWAITING:
            case.receive_human_input_sync(
                CaseNodeUpdate(payload={"approved": approved})
            )

    monkeypatch.setattr(
        "supervaizer.examples.hello_world_agent.time.sleep", answer_human_review
    )

    response = job_start(
        context=job.job_context,
        fields={"Enable human review": True},
    )

    case = _only_case(job.id)
    assert response.status == EntityStatus.COMPLETED
    assert response.message == "Completed 1 cases"
    assert case.status == EntityStatus.COMPLETED
    assert [update.name for update in case.updates] == [
        "Begin",
        "Progress",
        "Human Review",
        None,
        "End",
    ]
    assert case.updates[3].payload == {"approved": approved}
    assert case.final_delivery == {"result": "Case 1 completed"}
