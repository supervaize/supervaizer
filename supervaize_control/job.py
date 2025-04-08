# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Optional

from .__version__ import VERSION
from .common import SvBaseModel, singleton
from .parameter import Parameters


@singleton
class Jobs:
    """Global registry for all jobs, organized by agent"""

    def __init__(self) -> None:
        # Structure: {agent_name: {job_id: Job}}
        self.jobs_by_agent: dict[str, dict[str, "Job"]] = {}

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
            raise ValueError(
                f"Job with ID {job.id} already exists for agent {agent_name}"
            )

        self.jobs_by_agent[agent_name][job.id] = job

    def get_job(self, job_id: str, agent_name: str | None = None) -> "Job | None":
        """Get a job by its ID and optionally agent name

        Args:
            job_id (str): The ID of the job to get
            agent_name (str | None): The name of the agent. If None, searches all agents.

        Returns:
            Job | None: The job if found, None otherwise
        """
        if agent_name:
            # Search in specific agent's jobs
            return self.jobs_by_agent.get(agent_name, {}).get(job_id)

        # Search across all agents
        for agent_jobs in self.jobs_by_agent.values():
            if job_id in agent_jobs:
                return agent_jobs[job_id]
        return None

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


class JobConditions(SvBaseModel):
    max_cases: int | None = None
    max_duration: int | None = None  # in seconds
    max_cost: float | None = None
    stop_on_warning: bool = False
    stop_on_error: bool = True

    def check(self, cases: int, start_time: float, cost: float) -> tuple[bool, str]:
        """Check if the job conditions are met

        Args:
            cases (int): Number of cases processed so far
            start_time (float): Start time of the job - using time.perf_counter()
            cost (float): Cost incurred so far

        Returns:
            tuple[bool, str]: True if the job conditions are met, the job can continue, False otherwise, with explanation
        """
        if self.max_cases and cases >= self.max_cases:
            return (False, f"Max cases {self.max_cases} reached")

        duration = time.perf_counter() - start_time
        if self.max_duration and duration >= self.max_duration:
            return (False, f"Max duration {self.max_duration} seconds reached")

        if self.max_cost and cost >= self.max_cost:
            return (False, f"Max cost {self.max_cost} reached")

        return (True, "")


class JobContext(SvBaseModel):
    workspace_id: str
    job_id: str
    started_by: str
    started_at: datetime
    mission_id: str
    mission_name: str
    mission_context: Any = None
    job_conditions: Optional[JobConditions] = None


class JobStatus(str, Enum):
    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResponse(SvBaseModel):
    job_id: str
    status: JobStatus
    message: str
    payload: Optional[dict[str, Any]] = None


class JobModel(SvBaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    id: str
    agent_name: str
    status: "JobStatus"
    supervaize_context: "JobContext"
    payload: Any | None = None
    result: Any | None = None
    error: str | None = None
    responses: list["JobResponse"] = []
    finished_at: datetime | None = None


class Job(JobModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        Jobs().add_job(
            job=self,
        )

    def add_response(self, response: JobResponse) -> None:
        self.status = response.status
        self.payload = response.payload
        if response.status == JobStatus.COMPLETED:
            self.result = response.payload
            self.status = JobStatus.COMPLETED
            self.finished_at = datetime.now()
        if response.status == JobStatus.FAILED:
            self.finished_at = datetime.now()
            self.error = response.message
        self.responses.append(response)

    @classmethod
    def new(
        cls,
        supervaize_context: "JobContext",
        agent_name: str,
        parameters: Optional[Parameters] = None,
    ) -> "Job":
        """Create a new job

        Args:
            supervaize_context (JobContext): The context of the job
            agent_name (str): The name of the agent
            parameters (Parameters | None): Optional parameters for the job

        Returns:
            Job: The new job
        """
        job_id = supervaize_context.job_id or str(uuid.uuid4())
        job = cls(
            id=job_id,
            agent_name=agent_name,
            supervaize_context=supervaize_context,
            status=JobStatus.IN_PROGRESS,
        )
        return job
