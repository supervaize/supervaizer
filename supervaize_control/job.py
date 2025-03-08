import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel

from .__version__ import VERSION
from .common import singleton


class SupervaizeContextModel(BaseModel):
    workspace_id: str
    job_id: str
    started_by: str
    started_at: datetime
    mission_id: str
    mission_name: str
    mission_context: Any = None


@singleton
class Jobs:
    """Global registry for all jobs, organized by agent"""

    def __init__(self):
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


class JobStatus(Enum):
    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    payload: Any


class JobModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    id: str
    agent_name: str
    supervaize_context: SupervaizeContextModel
    result: Any | None = None
    payload: Any | None = None
    finished_at: datetime | None = None
    error: str | None = None
    status: JobStatus | None = None
    responses: list[JobResponse] = []


class Job(JobModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Jobs().add_job(
            job=self,
        )

    def add_response(self, response: JobResponse):
        self.status = response.status
        self.payload = response.payload
        if response.status == JobStatus.COMPLETED:
            self.result = response.payload
            self.finished_at = datetime.now()
        if response.status == JobStatus.FAILED:
            self.finished_at = datetime.now()
            self.error = response.message
        self.responses.append(response)

    @classmethod
    def new(cls, supervaize_context: "SupervaizeContextModel", agent_name: str):
        job_id = supervaize_context.job_id or str(uuid.uuid4())
        job = cls(
            id=job_id,
            agent_name=agent_name,
            supervaize_context=supervaize_context,
            status=JobStatus.IN_PROGRESS,
        )
        return job


class CaseModel(BaseModel):
    case_id: str
    case_name: str
    case_description: str
    case_status: JobStatus
    case_result: Any


class Case(CaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def new(cls, case_id: str, case_name: str, case_description: str):
        case = cls(
            case_id=case_id,
            case_name=case_name,
            case_description=case_description,
            case_status=JobStatus.IN_PROGRESS,
        )

        return case
