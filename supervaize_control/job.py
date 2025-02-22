from typing import ClassVar

from pydantic import BaseModel
from datetime import datetime
from .__version__ import VERSION


class JobModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    name: str
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    error: str | None = None
    result: str | None = None
