from typing import ClassVar, Any
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from .__version__ import VERSION


class JobContextModel(BaseModel):
    workspace_id: str
    job_id: str
    started_by: str
    started_at: datetime
    mission_id: str
    mission_name: str
    mission_context: Any = None


class JobStatus(Enum):
    FINAL = "final"
    INTERMEDIARY = "intermediary"
    START = "start"
    HUM = "Request Human"
    ERROR = "error"


class JobResponse(BaseModel):
    job_ref: str
    status: JobStatus
    message: str
    payload: Any


class JobModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    job_context: JobContextModel
    result: Any | None = None
    finished_at: datetime | None = None
    error: str | None = None
    status: JobStatus


class Job(JobModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def add_response(self, response: JobResponse):
        self.status = response.status
        if response.status == JobStatus.FINAL:
            self.result = response.payload
            self.finished_at = datetime.now()
        if response.status == JobStatus.ERROR:
            self.finished_at = datetime.now()
            self.error = response.message

    @classmethod
    def new(cls, job_context: "JobContextModel"):
        job = cls(
            job_context=job_context,
            status=JobStatus.START,
        )
        return job
