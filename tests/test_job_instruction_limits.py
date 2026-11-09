# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Pin limit boundaries and precedence through the public instruction model."""

import pytest
from pytest_mock import MockerFixture

from supervaizer.job import JobInstructions


@pytest.mark.parametrize(
    ("cases", "cost", "elapsed", "expected"),
    [
        (2, 5.0, 3.0, (False, "Max cases 2 reached")),
        (3, 9.0, 4.0, (False, "Max cases 2 reached")),
        (1, 5.0, 3.0, (False, "Max duration 3 seconds reached")),
        (1, 9.0, 4.0, (False, "Max duration 3 seconds reached")),
        (1, 5.0, 2.0, (False, "Max cost 5.0 reached")),
        (1, 9.0, 2.0, (False, "Max cost 5.0 reached")),
        (1, 4.99, 2.99, (True, "")),
    ],
)
def test_instruction_limits_keep_boundaries_and_precedence(
    mocker: MockerFixture,
    cases: int,
    cost: float,
    elapsed: float,
    expected: tuple[bool, str],
) -> None:
    instructions = JobInstructions(
        max_cases=2, max_duration=3, max_cost=5.0, job_start_time=100.0
    )
    mocker.patch("supervaizer.job.time.perf_counter", return_value=100.0 + elapsed)

    assert instructions.check(cases, cost) == expected
    assert instructions.job_start_time == 100.0


@pytest.mark.parametrize("limit", [None, 0])
def test_missing_or_zero_limits_allow_the_job(
    mocker: MockerFixture, limit: int | None
) -> None:
    instructions = JobInstructions(
        max_cases=limit, max_duration=limit, max_cost=limit, job_start_time=100.0
    )
    mocker.patch("supervaizer.job.time.perf_counter", return_value=1000.0)

    assert instructions.check(cases=1000, cost=1000.0) == (True, "")


@pytest.mark.parametrize("start", [None, 0.0])
def test_instruction_clock_starts_once_when_unset_or_zero(
    mocker: MockerFixture, start: float | None
) -> None:
    clock = mocker.patch(
        "supervaizer.job.time.perf_counter", side_effect=[10.0, 11.0, 12.0]
    )
    instructions = JobInstructions(job_start_time=start)

    assert instructions.check(cases=0, cost=0.0) == (True, "")
    assert instructions.check(cases=0, cost=0.0) == (True, "")
    assert instructions.job_start_time == 10.0
    assert clock.call_count == 3
