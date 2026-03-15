# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Minimal Hello World agent implementation for local test mode.

Used when running `supervaizer start --local` without Studio credentials.
Provides job_start, job_stop, job_status that work without Case/Account.
"""

import random
import time

import shortuuid

from supervaizer.account import Account
from supervaizer.case import Case, CaseNodeUpdate, Cases
from supervaizer.common import ApiSuccess, log
from supervaizer.job import JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus

STEPS = ["Begin", "Progress", "End"]


class _LocalAccount(Account):
    """No-op account for local mode — skips all Studio HTTP calls."""

    def send_event(self, sender, event):
        return ApiSuccess(message="local-noop", detail=None)


_local_account = _LocalAccount(
    workspace_id="local",
    api_key="local",
    api_url="http://localhost",
)


def _job_id_from_params(params: dict) -> str:
    context = params.get("context")
    if context is None:
        return "local-job"
    if hasattr(context, "job_id"):
        return getattr(context, "job_id", "local-job")
    return context.get("job_id", "local-job") if isinstance(context, dict) else "local-job"


def job_start(**kwargs) -> JobResponse:
    """Run a multi-case greeting job with simulated step durations."""
    job_id = _job_id_from_params(kwargs)
    fields = kwargs.get("fields") or {}
    n = int(fields.get("How many times to say hello", 1))
    n = max(0, min(n, 100))

    log.info(f"Starting job with {n} cases")

    for case_idx in range(1, n + 1):
        case_name = f"Hello case {case_idx}"
        log.info(f"--- Case {case_idx}/{n} ---")

        case = Case(
            id=shortuuid.uuid(),
            job_id=job_id,
            name=case_name,
            account=_local_account,
            description=f"Greeting case {case_idx} of {n}",
            status=EntityStatus.IN_PROGRESS,
        )

        # Link case to job
        job = Jobs().get_job(job_id)
        if job:
            job.add_case_id(case.id)

        for step_idx, step_name in enumerate(STEPS, start=1):
            duration = round(random.uniform(0.5, 3.0), 2)
            log.info(f"Case {case_idx}: starting step {step_idx} ({step_name})")
            time.sleep(duration)
            msg = f"The step {step_idx} ({step_name}) in case {case_idx} lasted {duration} s"
            log.info(msg)
            case.update(CaseNodeUpdate(
                name=step_name,
                payload={"message": msg, "duration": duration},
            ))

        case.close({"result": f"Case {case_idx} completed"})

    log.info(f"Job completed: {n} cases processed")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.COMPLETED,
        message=f"Completed {n} cases",
    )


def job_stop(**kwargs) -> JobResponse:
    """Stop handler for local Hello World agent."""
    job_id = kwargs.get("job_id") or _job_id_from_params(kwargs)
    log.info(f"Job stopped: {job_id}")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.STOPPED,
        message="Stopped",
    )


def job_status(**kwargs) -> JobResponse:
    """Status handler for local Hello World agent."""
    job_id = kwargs.get("job_id") or _job_id_from_params(kwargs)
    log.info(f"Job status: {job_id}")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.STOPPED,
        message="idle",
    )
