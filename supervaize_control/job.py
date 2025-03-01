from typing import ClassVar, Any
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from .__version__ import VERSION


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
    name: str
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: JobStatus
    error: str | None = None
    result: Any | None = None


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
    def new(cls, response: JobResponse):
        print(response)
        job = cls(
            name=f"Job {response.job_ref}",
            id=response.job_ref,
            started_at=datetime.now(),
            status=response.status,
            result=response.payload,
        )
        return job
