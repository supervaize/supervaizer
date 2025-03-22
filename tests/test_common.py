# Copyright (c) 2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from supervaize_control.common import ApiError, ApiSuccess

import json


def test_api_success_basic():
    """Test basic ApiSuccess functionality"""
    success = ApiSuccess(detail={"test": "data"}, message="success message")

    assert success.detail == {"test": "data"}
    assert success.message == "success message"
    assert success.code == "200"  # Default code

    # Verify JSON serialization
    json_data = json.loads(success.json_return)
    assert json_data["detail"] == {"test": "data"}
    assert json_data["message"] == "success message"


def test_api_error_basic():
    """Test basic ApiError functionality"""
    error = ApiError(message="error message", detail={"error": "details"}, code="400")

    assert error.message == "error message"
    assert error.detail == {"error": "details"}
    assert error.code == "400"

    # Verify JSON serialization
    json_data = json.loads(error.json_return)
    assert json_data["message"] == "error message"
    assert json_data["detail"] == {"error": "details"}


def test_api_error_with_exception():
    """Test ApiError with exception handling"""
    test_exception = ValueError("test error")
    error = ApiError(message="error occurred", exception=test_exception)

    json_data = json.loads(error.json_return)
    assert json_data["message"] == "error occurred"
    assert json_data["exception"]["type"] == "ValueError"
    assert json_data["exception"]["message"] == "test error"
    assert "traceback" in json_data["exception"]


def test_api_success_with_json_string_detail():
    """Test ApiSuccess with JSON string detail containing escaped quotes"""
    # Test with a JSON string containing escaped quotes
    json_detail = (
        '{"message": "Test \\"quoted\\" message", "data": "value with \\"quotes\\""}'
    )
    success = ApiSuccess(message="success", detail=json_detail)

    # Verify the JSON was properly decoded
    assert success.detail == {
        "message": 'Test "quoted" message',
        "data": 'value with "quotes"',
    }

    # Verify the decoded data is properly re-serialized
    json_data = json.loads(success.json_return)
    assert json_data["detail"]["message"] == 'Test "quoted" message'
    assert json_data["detail"]["data"] == 'value with "quotes"'
