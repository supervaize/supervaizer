from typing import ClassVar, Any
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from .__version__ import VERSION


class SupervaizeContextModel(BaseModel):
    workspace_id: str
    job_id: str
    started_by: str
    started_at: datetime
    mission_id: str
    mission_name: str
    mission_context: Any = None


class JobStatus(Enum):
    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResponse(BaseModel):
    job_ref: str
    status: JobStatus
    message: str
    payload: Any


class JobModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    supervaize_context: SupervaizeContextModel
    result: Any | None = None
    payload: Any | None = None
    finished_at: datetime | None = None
    error: str | None = None
    status: JobStatus


class Job(JobModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def add_response(self, response: JobResponse):
        self.status = response.status
        self.payload = response.payload
        if response.status == JobStatus.COMPLETED:
            self.result = response.payload
            self.finished_at = datetime.now()
        if response.status == JobStatus.FAILED:
            self.finished_at = datetime.now()
            self.error = response.message

    @classmethod
    def new(cls, supervaize_context: "SupervaizeContextModel"):
        job = cls(
            supervaize_context=supervaize_context,
            status=JobStatus.IN_PROGRESS,
        )
        return job
