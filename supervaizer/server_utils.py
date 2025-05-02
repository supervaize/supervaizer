# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from datetime import datetime
from enum import Enum

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger as log
from pydantic import BaseModel


class ErrorType(str, Enum):
    """Enumeration of possible error types"""

    JOB_NOT_FOUND = "job_not_found"
    JOB_ALREADY_EXISTS = "job_already_exists"
    AGENT_NOT_FOUND = "agent_not_found"
    INVALID_REQUEST = "invalid_request"
    INTERNAL_ERROR = "internal_error"
    INVALID_PARAMETERS = "invalid_parameters"


class ErrorResponse(BaseModel):
    """Standard error response model"""

    error: str
    error_type: ErrorType
    detail: str | None = None
    timestamp: datetime = datetime.now()
    status_code: int


def create_error_response(
    error_type: ErrorType, detail: str, status_code: int, traceback: str | None = None
) -> JSONResponse:
    """Helper function to create consistent error responses"""
    error_response = ErrorResponse(
        error=error_type.value.replace("_", " ").title(),
        error_type=error_type,
        detail=detail,
        status_code=status_code,
    )
    log.error(detail)
    if traceback:
        log.error(traceback)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_response),
    )
