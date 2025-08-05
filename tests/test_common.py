# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import json
from typing import Any, Dict, Optional

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import Field

from supervaizer.common import (
    ApiError,
    ApiSuccess,
    SvBaseModel,
    decrypt_value,
    encrypt_value,
    singleton,
)


def test_sv_base_model() -> None:
    """Test SvBaseModel functionality"""

    class TestModel(SvBaseModel):
        name: str = Field(default="test")
        value: int = Field(default=42)

    model = TestModel()

    # Test to_dict property
    dict_data = model.to_dict
    assert dict_data == {"name": "test", "value": 42}

    # Test to_json property
    json_data = json.loads(model.to_json)
    assert json_data == {"name": "test", "value": 42}


def test_api_success_basic() -> None:
    """Test basic ApiSuccess functionality"""
    success = ApiSuccess(detail={"test": "data"}, message="success message")

    assert success.detail == {"test": "data"}
    assert success.message == "success message"
    assert success.code == "200"  # Default code

    # Verify JSON serialization
    json_data = json.loads(success.json_return)
    assert json_data["detail"] == {"test": "data"}
    assert json_data["message"] == "success message"
    assert json_data["log_message"] == "✅ success message"

    assert repr(success) == "ApiSuccess (success message)"
    json_str = json.dumps({
        "message": "success message",
        "code": "200",
        "detail": {"test": "data"},
        "id": None,
        "log_message": "\u2705 success message",
    })
    assert str(success) == json_str


def test_api_error_basic() -> None:
    """Test basic ApiError functionality"""
    error = ApiError(message="error message", detail={"error": "details"}, code="400")

    assert error.message == "error message"
    assert error.detail == {"error": "details"}
    assert error.code == "400"

    # Verify JSON serialization
    json_data = json.loads(error.json_return)
    assert json_data["message"] == "error message"
    assert json_data["detail"] == {"error": "details"}


def test_api_error_with_exception() -> None:
    """Test ApiError with exception handling"""
    test_exception = ValueError("test error")
    error = ApiError(message="error occurred", exception=test_exception)

    json_data = json.loads(error.json_return)
    assert json_data["message"] == "error occurred"
    assert json_data["exception"]["type"] == "ValueError"
    assert json_data["exception"]["message"] == "test error"
    assert "traceback" in json_data["exception"]


def test_api_success_with_json_string_detail() -> None:
    """Test ApiSuccess with JSON string detail containing escaped quotes"""
    # Test with a JSON string containing escaped quotes
    json_detail = (
        '{"message": "Test \\"quoted\\" message", "data": "value with \\"quotes\\""}'
    )
    success = ApiSuccess(message="success", detail=json_detail)

    # Verify the JSON was properly decoded
    assert success.detail == {
        "object": {
            "message": 'Test "quoted" message',
            "data": 'value with "quotes"',
        }
    }

    # Verify the decoded data is properly re-serialized
    json_data = json.loads(success.json_return)
    assert json_data["detail"]["object"]["message"] == 'Test "quoted" message'
    assert json_data["detail"]["object"]["data"] == 'value with "quotes"'


def test_api_success() -> None:
    """Test ApiSuccess with ID in detail string"""
    detail = '{"id": "123", "data": "test"}'
    success = ApiSuccess(message="success", detail=detail)
    assert success.id == "123"
    assert success.log_message == "✅ success : 123"

    """Test ApiSuccess with empty JSON string"""
    success = ApiSuccess(message="success", detail="{}")
    assert getattr(success, "id", None) is None
    assert success.log_message == "✅ success"

    """Test ApiSuccess with JSON without ID"""
    json_detail: Dict[str, str] = {"data": "test"}
    success = ApiSuccess(message="success", detail=json_detail)
    assert success.log_message == "✅ success"

    """Test ApiSuccess with dict detail"""
    detail_dict = {"data": "test"}
    success = ApiSuccess(message="success", detail=detail_dict)
    assert success.log_message == "✅ success"


def test_api_error() -> None:
    """Test ApiError"""
    error = ApiError(message="error message", detail={"error": "details"}, code="400")
    assert error.message == "error message"
    assert error.detail == {"error": "details"}
    assert error.code == "400"

    # Test the dict property
    json_data = error.dict
    assert json_data["message"] == "error message"
    assert json_data["detail"] == {"error": "details"}
    assert json_data["code"] == "400"
    assert json_data["url"] == ""
    assert json_data["payload"] is None

    # Test with an exception that has custom attributes
    class CustomException(Exception):
        def __init__(self) -> None:
            super().__init__()
            self.custom_attr = '{"key": "value"}'
            self.response: Optional[Any] = None

    exc = CustomException()
    error = ApiError(message="error", exception=exc)

    # Verify exception attributes are captured
    assert error.dict["exception"]["attributes"]["custom_attr"] == {"key": "value"}
    assert error.dict["exception"]["type"] == "CustomException"
    assert error.dict["exception"]["message"] == ""

    """Test ApiError with exception containing response"""

    class ResponseException(CustomException):
        def __init__(self, status_code: int, response_text: str) -> None:
            super().__init__()
            self.response = type(
                "Response", (), {"status_code": status_code, "text": response_text}
            )

    # Test with JSON response
    exc = ResponseException(404, '{"error": "not found"}')
    error = ApiError(message="error", exception=exc)
    json_data = json.loads(error.json_return)

    assert error.code == "404"
    assert json_data["exception"]["response"] == {"error": "not found"}

    # Test with non-JSON response
    exc = ResponseException(500, "Internal Server Error")
    error = ApiError(message="error", exception=exc)
    json_data = json.loads(error.json_return)

    assert error.code == "500"
    assert "response" not in json_data["exception"]

    """Test ApiError with empty exception message"""
    error = ApiError(message="error", exception=Exception())
    assert error.log_message == "❌ error : "


def test_singleton() -> None:
    """Test singleton decorator"""

    @singleton
    class TestClass:
        def __init__(self) -> None:
            self.value = 0

    # Should return same instance
    instance1 = TestClass()
    instance2 = TestClass()

    assert instance1 is instance2

    # Should share state
    instance1.value = 42
    assert instance2.value == 42


def test_encrypt_decrypt() -> None:
    """Test encryption and decryption of values"""
    # Generate key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Test string
    test_str = "test string"
    encrypted = encrypt_value(test_str, public_key)
    decrypted = decrypt_value(encrypted, private_key)
    assert isinstance(encrypted, str)
    assert isinstance(decrypted, str)
    assert decrypted == test_str

    # Test dict
    test_dict = {"key": "value"}
    encrypted_dict = encrypt_value(json.dumps(test_dict), public_key)
    decrypted_dict = json.loads(decrypt_value(encrypted_dict, private_key))
    assert isinstance(encrypted_dict, str)
    assert isinstance(decrypted_dict, dict)
    assert decrypted_dict == test_dict

    # Test encryption failure
    with pytest.raises(AttributeError, match="object has no attribute"):
        encrypt_value("test", None)  # type: ignore

    # Test decryption failure
    with pytest.raises(ValueError, match="Incorrect padding"):
        decrypt_value("invalid", private_key)


def test_sv_base_model_json_conversion() -> None:
    """Test SvBaseModel with datetime serialization using mode='json'"""
    from datetime import datetime

    class ModelWithDateTime(SvBaseModel):
        name: str = Field(default="test")
        timestamp: datetime = Field(
            default_factory=lambda: datetime(2024, 1, 1, 12, 0, 0)
        )

    model = ModelWithDateTime()

    # Test to_dict converts datetime to ISO format string
    dict_data = model.to_dict
    assert dict_data["name"] == "test"
    assert dict_data["timestamp"] == "2024-01-01T12:00:00"
    assert isinstance(
        dict_data["timestamp"], str
    )  # Verify it's a string, not a datetime object

    # Test to_json also handles the datetime correctly
    json_data = json.loads(model.to_json)
    assert json_data["timestamp"] == "2024-01-01T12:00:00"
