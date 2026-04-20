# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

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
from typing import Any

import shortuuid

from supervaizer.account import Account
from supervaizer.case import Case, CaseNodeUpdate
from supervaizer.common import ApiSuccess, log
from supervaizer.job import JobInstructions, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus

STEPS_WITH_HITL = ["Begin", "Progress", "Human Review", "End"]
STEPS_WITHOUT_HITL = ["Begin", "Progress", "End"]
HITL_POLL_INTERVAL = 1.0  # seconds between polls while waiting for human input


class _LocalAccount(Account):
    """No-op account for local mode — skips all Studio HTTP calls."""

    def send_event(self, sender: Any, event: Any) -> ApiSuccess:
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
        return context.job_id
    if isinstance(context, dict):
        return context.get("job_id", "local-job")
    return "local-job"


def job_start(**kwargs: Any) -> JobResponse:
    """Run a multi-case greeting job with simulated step durations."""
    job_id = _job_id_from_params(kwargs)
    fields = kwargs.get("fields") or {}
    n = int(fields.get("How many times to say hello", 1))
    n = max(0, min(n, 100))
    enable_hitl = str(fields.get("Enable human review", False)).lower() in (
        "true",
        "on",
        "1",
        "yes",
    )
    steps = STEPS_WITH_HITL if enable_hitl else STEPS_WITHOUT_HITL

    log.info(f"Starting job with {n} cases (HITL: {enable_hitl})")

    job_instructions = JobInstructions(max_cases=n)
    cases_done = 0
    stopped = False

    def _is_job_stopped() -> bool:
        """Check if the job was stopped externally."""
        job = Jobs().get_job(job_id)
        return job is not None and job.status in (
            EntityStatus.STOPPED,
            EntityStatus.CANCELLED,
        )

    for case_idx in range(1, n + 1):
        # Check job instructions before each case
        can_continue, explanation = job_instructions.check(cases=cases_done, cost=0)
        if not can_continue or _is_job_stopped():
            log.info(
                f"Job stopped before case {case_idx}: {explanation or 'stopped by user'}"
            )
            stopped = True
            break

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

        case_interrupted = False
        for step_idx, step_name in enumerate(steps, start=1):
            # Check job status before each step
            if _is_job_stopped():
                log.info(f"Job stopped during case {case_idx} at step {step_name}")
                case_interrupted = True
                break

            if step_name == "Human Review":
                log.info(f"Case {case_idx}: requesting human input")
                hitl_update = CaseNodeUpdate(
                    name="Human Review",
                    payload={
                        "supervaizer_form": {
                            "question": f"Review case {case_idx}: should we continue?",
                            "answer": {
                                "fields": [
                                    {
                                        "name": "approved",
                                        "description": "Approve this case to continue",
                                        "type": "bool",
                                        "field_type": "BooleanField",
                                        "required": True,
                                    },
                                    {
                                        "name": "comment",
                                        "description": "Optional reviewer comment",
                                        "type": "str",
                                        "field_type": "CharField",
                                        "required": False,
                                    },
                                ]
                            },
                        },
                        "message": f"Waiting for human review on case {case_idx}",
                    },
                )
                case.request_human_input(hitl_update, message=f"Review case {case_idx}")

                # Poll until human answers or job is stopped
                while case.status == EntityStatus.AWAITING:
                    if _is_job_stopped():
                        log.info(f"Job stopped while awaiting HITL on case {case_idx}")
                        case_interrupted = True
                        break
                    time.sleep(HITL_POLL_INTERVAL)

                if case_interrupted:
                    break
                log.info(f"Case {case_idx}: human input received, continuing")
            else:
                duration = round(random.uniform(0.5, 3.0), 2)
                log.info(f"Case {case_idx}: starting step {step_idx} ({step_name})")
                time.sleep(duration)
                msg = f"The step {step_idx} ({step_name}) in case {case_idx} lasted {duration} s"
                log.info(msg)
                case.update(
                    CaseNodeUpdate(
                        name=step_name,
                        payload={"message": msg, "duration": duration},
                    )
                )

        if case_interrupted:
            log.info(f"Case {case_idx} interrupted")
            stopped = True
            break

        case.close({"result": f"Case {case_idx} completed"})
        cases_done += 1

    if stopped:
        log.info(f"Job stopped: {cases_done}/{n} cases completed")
        return JobResponse(
            job_id=job_id,
            status=EntityStatus.STOPPED,
            message=f"Stopped after {cases_done}/{n} cases",
        )

    log.info(f"Job completed: {n} cases processed")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.COMPLETED,
        message=f"Completed {n} cases",
    )


def human_answer(**kwargs: Any) -> JobResponse:
    """Handle HITL answer submission."""
    job_id = kwargs.get("job_id") or _job_id_from_params(kwargs)
    case_id = kwargs.get("case_id", "")
    fields = kwargs.get("fields") or {}
    log.info(f"Human answer received for case {case_id}: {fields}")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.IN_PROGRESS,
        message="Human answer processed",
        payload={"case_id": case_id, "answer": fields},
    )


def job_stop(**kwargs: Any) -> JobResponse:
    """Stop handler for local Hello World agent."""
    job_id = kwargs.get("job_id") or _job_id_from_params(kwargs)
    log.info(f"Job stopped: {job_id}")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.STOPPED,
        message="Stopped",
    )


def job_status(**kwargs: Any) -> JobResponse:
    """Status handler for local Hello World agent."""
    job_id = kwargs.get("job_id") or _job_id_from_params(kwargs)
    log.info(f"Job status: {job_id}")
    return JobResponse(
        job_id=job_id,
        status=EntityStatus.STOPPED,
        message="idle",
    )
