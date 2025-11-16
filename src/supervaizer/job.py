# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import time
import traceback
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from supervaizer.__version__ import VERSION
from supervaizer.common import SvBaseModel, log, singleton
from supervaizer.lifecycle import (
    EntityEvents,
    EntityStatus,
    Lifecycle,
)
from supervaizer.storage import storage_manager

if TYPE_CHECKING:
    pass


@singleton
class Jobs:
    """Global registry for all jobs, organized by agent."""

    def __init__(self) -> None:
        # Structure: {agent_name: {job_id: Job}}
        self.jobs_by_agent: dict[str, dict[str, "Job"]] = {}

    def reset(self) -> None:
        self.jobs_by_agent.clear()

    def add_job(self, job: "Job") -> None:
        """Add a job to the registry under its agent

        Args:
            job (Job): The job to add

        Raises:
            ValueError: If job with same ID already exists for this agent
        """
        agent_name = job.agent_name

        # Initialize agent's job dict if not exists
        if agent_name not in self.jobs_by_agent:
            self.jobs_by_agent[agent_name] = {}

        # Check if job already exists for this agent
        if job.id in self.jobs_by_agent[agent_name]:
            log.warning(f"Job ID '{job.id}' already exists for agent {agent_name}.")

        self.jobs_by_agent[agent_name][job.id] = job

    def get_job(
        self,
        job_id: str,
        agent_name: str | None = None,
        include_persisted: bool = False,
    ) -> "Job | None":
        """Get a job by its ID and optionally agent name

        Args:
            job_id (str): The ID of the job to get
            agent_name (str | None): The name of the agent. If None, searches all agents.
            include_persisted (bool): Whether to include persisted jobs. Defaults to False.

        Returns:
            Job | None: The job if found, None otherwise
        """
        found_job = None

        if agent_name:
            # Search in specific agent's jobs
            found_job = self.jobs_by_agent.get(agent_name, {}).get(job_id)

        # Search across all agents
        for agent_jobs in self.jobs_by_agent.values():
            if job_id in agent_jobs:
                found_job = agent_jobs[job_id]

        if include_persisted:
            job_from_storage = storage_manager.get_object_by_id("Job", job_id)
            if job_from_storage:
                found_job = Job(**job_from_storage)
        return found_job

    def get_agent_jobs(self, agent_name: str) -> dict[str, "Job"]:
        """Get all jobs for a specific agent

        Args:
            agent_name (str): The name of the agent

        Returns:
            dict[str, Job]: Dictionary of jobs for this agent, empty if agent not found
        """
        return self.jobs_by_agent.get(agent_name, {})

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists in any agent's registry"""
        return any(job_id in jobs for jobs in self.jobs_by_agent.values())


class JobInstructions(SvBaseModel):
    max_cases: int | None = None
    max_duration: int | None = None  # in seconds
    max_cost: float | None = None
    stop_on_warning: bool = False
    stop_on_error: bool = True

    job_start_time: float | None = None

    def check(self, cases: int, cost: float) -> tuple[bool, str]:
        """Check if the job conditions are met

        Args:
            cases (int): Number of cases processed so far
            start_time (float): Start time of the job - using time.perf_counter()

        Returns:
            tuple[bool, str]: True if job can continue, False if it should stop,
                with explanation message
        """
        if not self.job_start_time:
            self.job_start_time = time.perf_counter()
        if self.max_cases and cases >= self.max_cases:
            return (False, f"Max cases {self.max_cases} reached")

        duration = time.perf_counter() - self.job_start_time
        if self.max_duration and duration >= self.max_duration:
            return (False, f"Max duration {self.max_duration} seconds reached")

        if self.max_cost and cost >= self.max_cost:
            return (False, f"Max cost {self.max_cost} reached")

        return (True, "")

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the job instructions"""
        return {
            "max_cases": self.max_cases,
            "max_duration": self.max_duration,
            "max_cost": self.max_cost,
            "stop_on_warning": self.stop_on_warning,
            "stop_on_error": self.stop_on_error,
        }


class JobContext(SvBaseModel):
    workspace_id: str
    job_id: str
    started_by: str
    started_at: datetime
    mission_id: str
    mission_name: str
    mission_context: Any = None
    job_instructions: Optional[JobInstructions] = None

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the job context"""
        return {
            "workspace_id": self.workspace_id,
            "job_id": self.job_id,
            "started_by": self.started_by,
            "started_at": self.started_at.isoformat() if self.started_at else "",
            "mission_id": self.mission_id,
            "mission_name": self.mission_name,
            "mission_context": self.mission_context,
            "job_instructions": self.job_instructions.registration_info
            if self.job_instructions
            else None,
        }


class JobResponse(SvBaseModel):
    job_id: str
    status: EntityStatus
    message: str
    payload: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    def __init__(
        self,
        job_id: str,
        status: EntityStatus,
        message: str,
        payload: Optional[dict[str, Any]] = None,
        error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        log.debug(
            f"[JobResponse __init__] job_id={job_id}, status={status}, message={message}, payload={payload}, error={error}, kwargs={kwargs}"
        )
        if error:
            error_message = str(error)
            error_traceback = traceback.format_exc()
        else:
            error_message = error_traceback = ""
        kwargs["job_id"] = job_id
        kwargs["status"] = status
        kwargs["message"] = message
        kwargs["payload"] = payload
        kwargs["error_message"] = error_message
        kwargs["error_traceback"] = error_traceback
        super().__init__(**kwargs)

        if error:
            log.error(
                f"[Job Response] Execution failed - Job ID <{self.job_id}>: {self.error_message}"
            )
            log.error(self.error_traceback)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the job response"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "message": self.message,
            "payload": self.payload,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
        }


class AbstractJob(SvBaseModel):
    supervaizer_VERSION: ClassVar[str] = VERSION
    id: str
    name: str
    agent_name: str
    status: EntityStatus
    job_context: JobContext
    payload: Any | None = None
    result: Any | None = None
    error: str | None = None
    responses: list["JobResponse"] = []
    finished_at: datetime | None = None
    created_at: datetime | None = None
    agent_parameters: list[dict[str, Any]] | None = None
    case_ids: list[str] = []  # Foreign key relationship to cases


class Job(AbstractJob):
    """
    Jobs are typically created by the platform and are not created by the agent.

    Args:
        id (str): Unique identifier for the job - provided by the platform
        agent_name (str): Name (slug) of the agent running the job
        status (EntityStatus): Current status of the job
        job_context (JobContext): Context information for the job
        payload (Any, optional): Job payload data. Defaults to None
        result (Any, optional): Job result data. Defaults to None
        error (str, optional): Error message if job failed. Defaults to None
        responses (list[JobResponse], optional): List of job responses. Defaults to empty list
        finished_at (datetime, optional): When job completed. Defaults to None
        created_at (datetime, optional): When job was created. Defaults to None
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.created_at = datetime.now()
        Jobs().add_job(
            job=self,
        )
        # Persist job to storage

        storage_manager.save_object("Job", self.to_dict)

    def add_response(self, response: JobResponse) -> None:
        """Add a response to the job and update status based on the event lifecycle.

        Args:
            response: The response to add
        """
        if response.status in Lifecycle.get_terminal_states():
            self.finished_at = datetime.now()

        # Update payload
        self.payload = response.payload
        self.status = response.status
        # Additional handling for completed or failed jobs
        if response.status == EntityStatus.COMPLETED:
            self.result = response.payload

        if response.status == EntityStatus.FAILED:
            self.error = response.message

        self.responses.append(response)

        # Persist updated job to storage

        storage_manager.save_object("Job", self.to_dict)

    def add_case_id(self, case_id: str) -> None:
        """Add a case ID to this job's case list.

        Args:
            case_id: The case ID to add
        """
        if case_id not in self.case_ids:
            self.case_ids.append(case_id)
            log.debug(f"[Job add_response] Added case {case_id} to job {self.id}")
            # Persist updated job to storage
            storage_manager.save_object("Job", self.to_dict)

    def remove_case_id(self, case_id: str) -> None:
        """Remove a case ID from this job's case list.

        Args:
            case_id: The case ID to remove
        """
        if case_id in self.case_ids:
            self.case_ids.remove(case_id)
            log.debug(f"Removed case {case_id} from job {self.id}")
            # Persist updated job to storage
            storage_manager.save_object("Job", self.to_dict)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the job"""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "job_context": self.job_context.registration_info,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "responses": [response.registration_info for response in self.responses],
            "finished_at": self.finished_at.isoformat() if self.finished_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "case_ids": self.case_ids,
        }

    @classmethod
    def new(
        cls,
        job_context: "JobContext",
        agent_name: str,
        agent_parameters: Optional[list[dict[str, Any]]] = None,
        name: Optional[str] = None,
    ) -> "Job":
        """Create a new job

        Args:
            job_context (JobContext): The context of the job
            agent_name (str): The name of the agent
            agent_parameters (list[dict[str, Any]] | None): Optional parameters for the job
            name (str | None): Optional name for the job, defaults to mission name if not provided

        Returns:
            Job: The new job
        """
        job_id = job_context.job_id or str(uuid.uuid4())
        # Use provided name or fallback to mission name from context
        job_name = name or job_context.mission_name

        # Ensure agent_parameters is a list of dicts, not nested incorrectly
        if agent_parameters is not None:
            # If it's a list but the first element is also a list, unwrap it
            if isinstance(agent_parameters, list) and len(agent_parameters) > 0:
                if isinstance(agent_parameters[0], list):
                    # Unwrap nested list: [[{...}, {...}]] -> [{...}, {...}]
                    agent_parameters = agent_parameters[0]
            # Ensure all elements are dicts
            if not all(isinstance(p, dict) for p in agent_parameters):
                raise ValueError(
                    f"agent_parameters must be a list of dictionaries, got: {type(agent_parameters)}"
                )

        job = cls(
            id=job_id,
            name=job_name,
            agent_name=agent_name,
            job_context=job_context,
            status=EntityStatus.STOPPED,
            agent_parameters=agent_parameters,
        )

        # Transition from STOPPED to IN_PROGRESS
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(job, EntityEvents.START_WORK)

        return job
