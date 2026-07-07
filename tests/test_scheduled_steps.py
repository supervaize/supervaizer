# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from datetime import UTC, datetime

from supervaizer import Account, Case, EntityStatus, Job, JobContext
from supervaizer.case import Cases
from supervaizer.job import Jobs
from supervaizer.scheduled_steps import _resolve_case_job


def test_resolve_case_job_uses_case_membership_for_duplicate_job_ids(
    account_fixture: Account,
) -> None:
    Cases().reset()
    Jobs().reset()
    job_id = "shared-job-id"
    first_context = JobContext(
        workspace_id="test-workspace",
        job_id=job_id,
        started_by="test-user",
        started_at=datetime.now(UTC),
        mission_id="first-mission",
        mission_name="First Mission",
    )
    second_context = first_context.model_copy(
        update={"mission_id": "second-mission", "mission_name": "Second Mission"}
    )
    first_job = Job.new(job_context=first_context, agent_name="first-agent")
    second_job = Job.new(job_context=second_context, agent_name="second-agent")
    case = Case(
        id="second-agent-case",
        job_id=job_id,
        account=account_fixture,
        status=EntityStatus.IN_PROGRESS,
        name="Second Agent Case",
        description="Owned by the second agent",
    )
    second_job.add_case_id(case.id)

    assert first_job.id == second_job.id
    assert _resolve_case_job(Jobs(), case) is second_job

    Cases().reset()
    Jobs().reset()
