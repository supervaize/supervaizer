# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
from typing import TYPE_CHECKING, Any, Dict, Optional


from supervaizer.common import decrypt_value, log
from supervaizer.event import JobFinishedEvent
from supervaizer.job import Job, Jobs
from supervaizer.lifecycle import EntityStatus

if TYPE_CHECKING:
    from fastapi import BackgroundTasks

    from supervaizer.agent import Agent
    from supervaizer.job import JobContext
    from supervaizer.server import Server


async def service_job_start(
    server: "Server",
    background_tasks: "BackgroundTasks",
    agent: "Agent",
    sv_context: "JobContext",
    job_fields: Dict[str, Any],
    encrypted_agent_parameters: Optional[str] = None,
) -> "Job":
    """
    Create a new job and schedule its execution.

    Args:
        server: The server instance
        background_tasks: FastAPI background tasks
        agent: The agent to run the job
        sv_context: The supervaize context
        job_fields: Fields for the job
        encrypted_agent_parameters: Optional encrypted parameters

    Returns:
        The created job
    """
    agent_parameters = None
    # If agent has parameters_setup defined, validate parameters
    if getattr(agent, "parameters_setup") and encrypted_agent_parameters:
        agent_parameters_str = decrypt_value(
            encrypted_agent_parameters, server.private_key
        )
        agent_parameters = (
            json.loads(agent_parameters_str) if agent_parameters_str else None
        )

        # inspect(agent)
        log.debug(
            f"[service_job_start Decrypted parameters] : parameters = {agent_parameters}"
        )

    # Create and prepare the job
    new_saas_job = Job.new(
        job_context=sv_context,
        agent_name=agent.name,
        agent_parameters=agent_parameters,
        name=sv_context.job_id,
    )

    # Start the background execution
    background_tasks.add_task(
        agent.job_start, new_saas_job, job_fields, sv_context, server
    )
    return new_saas_job


def service_job_finished(job: Job, server: "Server") -> None:
    """
    Service to handle the completion of a job.

    Args:
        job: The job that has finished
        server: The server instance

    Tested in tests/test_job_service.py
    """
    assert server.supervisor_account is not None, "No account defined"
    account = server.supervisor_account
    event = JobFinishedEvent(
        job=job,
        account=account,
    )
    account.send_event(sender=job, event=event)


async def service_job_custom(
    method_name: str,
    server: "Server",
    background_tasks: "BackgroundTasks",
    agent: "Agent",
    sv_context: "JobContext",
    job_fields: Dict[str, Any],
    encrypted_agent_parameters: Optional[str] = None,
) -> "Job":
    """
    Create a new job and schedule its execution for a custom method.

    Args:
        server: The server instance
        background_tasks: FastAPI background tasks
        agent: The agent to run the job
        sv_context: The supervaize context
        job_fields: Fields for the job
        encrypted_agent_parameters: Optional encrypted parameters

    Returns:
        The created job
    """
    log.info(
        f"[service_job_custom] /custom/{method_name} [custom job] {agent.name} with params {job_fields}"
    )
    _agent_parameters: dict[str, Any] | None = None
    # If agent has parameters_setup defined, validate parameters
    if getattr(agent, "parameters_setup") and encrypted_agent_parameters:
        agent_parameters_str = decrypt_value(
            encrypted_agent_parameters, server.private_key
        )
        _agent_parameters = (
            json.loads(agent_parameters_str) if agent_parameters_str else None
        )
        log.debug("[Decrypted parameters] : parameters decrypted")

    # Create and prepare the job
    job_id = sv_context.job_id

    if not job_id:
        raise ValueError(
            "[service_job_custom] Job ID is required to start a custom job"
        )

    job = Jobs().get_job(job_id) or Job(
        id=job_id,
        job_context=sv_context,
        agent_name=agent.name,
        name=sv_context.mission_name,
        status=EntityStatus.STOPPED,
    )  # TODO clean the name
    # Start the background execution
    background_tasks.add_task(
        agent.job_start,
        job,
        job_fields,
        sv_context,
        server,
        method_name,
    )
    return job
