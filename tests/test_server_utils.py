# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from datetime import datetime

from fastapi.responses import JSONResponse

from supervaize_control.server_utils import (
    ErrorResponse,
    ErrorType,
    create_error_response,
)


def test_error_type_enum():
    assert ErrorType.JOB_NOT_FOUND == "job_not_found"
    assert ErrorType.JOB_ALREADY_EXISTS == "job_already_exists"
    assert ErrorType.AGENT_NOT_FOUND == "agent_not_found"
    assert ErrorType.INVALID_REQUEST == "invalid_request"
    assert ErrorType.INTERNAL_ERROR == "internal_error"
    assert ErrorType.INVALID_PARAMETERS == "invalid_parameters"


def test_error_response_model():
    error = ErrorResponse(
        error="Test Error",
        error_type=ErrorType.INVALID_REQUEST,
        detail="Test detail",
        status_code=400,
    )

    assert error.error == "Test Error"
    assert error.error_type == ErrorType.INVALID_REQUEST
    assert error.detail == "Test detail"
    assert error.status_code == 400
    assert isinstance(error.timestamp, datetime)


def test_create_error_response():
    response = create_error_response(
        error_type=ErrorType.JOB_NOT_FOUND, detail="Job 123 not found", status_code=404
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 404

    content = response.body.decode()
    assert "Job Not Found" in content
    assert "Job 123 not found" in content
    assert "job_not_found" in content


def test_create_error_response_without_detail():
    response = create_error_response(
        error_type=ErrorType.INTERNAL_ERROR, detail=None, status_code=500
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 500

    content = response.body.decode()
    assert "Internal Error" in content
