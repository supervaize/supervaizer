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
from supervaizer.contracts import SUPERVAIZER_V2_A2UI_VERSION
from supervaizer.job import JobInstructions, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus

STEPS_WITH_HITL = ["Begin", "Progress", "Human Review", "End"]
STEPS_WITHOUT_HITL = ["Begin", "Progress", "End"]
HITL_POLL_INTERVAL = 1.0  # seconds between polls while waiting for human input
HELLO_WORLD_A2UI_CATALOG_VERSION = "supervaizer-v2-local.0"


class _LocalAccount(Account):
    """No-op account for local mode — skips all Studio HTTP calls."""

    async def send_event(self, sender: Any, event: Any) -> ApiSuccess:
        return ApiSuccess(message="local-noop", detail=None)

    def send_event_sync(self, sender: Any, event: Any) -> ApiSuccess:
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
                case.request_human_input_sync(
                    hitl_update, message=f"Review case {case_idx}"
                )

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
                case.update_sync(
                    CaseNodeUpdate(
                        name=step_name,
                        payload={"message": msg, "duration": duration},
                    )
                )

        if case_interrupted:
            log.info(f"Case {case_idx} interrupted")
            stopped = True
            break

        case.close_sync({"result": f"Case {case_idx} completed"})
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


def handle_v2_surface(surface_request: Any) -> dict[str, Any]:
    """Return the local Hello World job.start A2UI document."""
    request = _request_dict(surface_request)
    surface = str(request.get("surface") or "").strip()
    return {
        "surface": surface,
        "a2ui_version": SUPERVAIZER_V2_A2UI_VERSION,
        "a2ui_catalog_version": HELLO_WORLD_A2UI_CATALOG_VERSION,
        "document": {
            "type": "Form",
            "id": "supervaizer.local.hello_world.job.start",
            "title": "Start Hello World",
            "fields": [
                {
                    "id": "count",
                    "label": "How many times to say hello",
                    "type": "number",
                    "required": True,
                    "default": 3,
                },
                {
                    "id": "enable_human_review",
                    "label": "Enable human review",
                    "type": "boolean",
                    "required": False,
                    "default": False,
                },
            ],
            "submit": {"action": "job.start", "label": "Start"},
            "preview": {"action": "job.start.preview"},
            "state": {"draft_session_id": request.get("draft_session_id")},
        },
    }


def handle_v2_action(action_request: Any) -> dict[str, Any]:
    """Dispatch minimal v2 actions for the local Hello World agent."""
    request = _request_dict(action_request)
    action = str(request.get("action") or "").strip()
    if action == "job.start.preview":
        return _ok_result("job.start.previewed", request_id=request.get("request_id"))
    if action != "job.start":
        return {
            "status": "error",
            "effects": [{"type": "action.unsupported", "action": action}],
        }

    response = job_start(
        fields=_legacy_job_start_fields(_action_input(request)),
        context={"job_id": request.get("job_id") or "local-v2-job"},
    )
    return {
        "status": "ok",
        "effects": [
            {
                "type": "job.started",
                "job_id": response.job_id,
                "status": _status_value(response.status),
                "message": response.message,
                "payload": response.payload,
            }
        ],
    }


def _legacy_job_start_fields(action_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "How many times to say hello": action_input.get(
            "count",
            action_input.get("How many times to say hello", 1),
        ),
        "Enable human review": action_input.get(
            "enable_human_review",
            action_input.get("Enable human review", False),
        ),
    }


def _ok_result(effect_type: str, **effect: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "effects": [{"type": effect_type, **effect}],
    }


def _action_input(request: dict[str, Any]) -> dict[str, Any]:
    value = request.get("input")
    return value if isinstance(value, dict) else {}


def _request_dict(request: Any) -> dict[str, Any]:
    if isinstance(request, dict):
        return request
    if hasattr(request, "model_dump"):
        return request.model_dump(mode="python")
    raise TypeError(f"Unsupported request type: {type(request).__name__}")


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status))
