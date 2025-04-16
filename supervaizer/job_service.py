import json
from typing import Optional, TYPE_CHECKING, Dict, Any
from .event import JobFinishedEvent
from .common import log, decrypt_value
from .job import Job

if TYPE_CHECKING:
    from .job import Job, JobContext
    from .server import Server
    from .agent import Agent
    from fastapi import BackgroundTasks


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
    agent_parameters: dict[str, Any] | None = None
    # If agent has parameters_setup defined, validate parameters
    if getattr(agent, "parameters_setup") and encrypted_agent_parameters:
        agent_parameters_str = decrypt_value(
            encrypted_agent_parameters, server.private_key
        )
        agent_parameters = (
            json.loads(agent_parameters_str) if agent_parameters_str else None
        )
        log.debug("[Decrypted parameters] : parameters decrypted")

    # Create and prepare the job
    new_saas_job = Job.new(
        job_context=sv_context,
        agent_name=agent.name,
        parameters=agent_parameters,
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
