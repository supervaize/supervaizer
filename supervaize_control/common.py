# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import base64
import json
import traceback
from datetime import datetime

import demjson3
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from loguru import logger
from pydantic import BaseModel

log = logger.bind(module="supervaize")


class SvBaseModel(BaseModel):
    """
    Base model for all Supervaize models.
    """

    model_config = {
        "json_schema_serialization_defaults": {datetime: lambda x: x.isoformat()}
    }

    @property
    def to_dict(self):
        return self.model_dump()

    @property
    def to_json(self):
        return self.model_dump_json()


class ApiResult:
    def __init__(self, message: str, detail: dict | str, code: str):
        self.message = message
        self.code = str(code)
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.json_return}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.message})"

    @property
    def dict(self) -> dict:
        return {key: value for key, value in self.__dict__.items()}

    @property
    def json_return(self) -> str:
        return json.dumps(self.dict)


class ApiSuccess(ApiResult):
    """
    ApiSuccess is a class that extends ApiResult.
    It is used to return a success response from the API.

    Tested in tests/test_common.py
    """

    def __init__(self, message: str, detail: dict | str, code: str = 200):
        super().__init__(message, detail, code)
        if isinstance(detail, str):
            result = demjson3.decode(detail, return_errors=True)
            self.detail = result.object
            print(f"result.object: {result.object}")
            self.id = result.object.get("id") or None
            self.log_message = (
                f"✅ {message} : {self.id}" if self.id else f"✅ {message}"
            )
        else:
            self.detail = detail
            self.log_message = f"✅ {message}"


class ApiError(ApiResult):
    """
    ApiError is a class that extends ApiResult.
    It can be used to return an error response from the API.
    Note : not really useful for the moment, as API errors raise exception.

    Tested in tests/test_common.py
    """

    def __init__(
        self,
        message: str,
        code: str = "",
        detail: dict = {},
        exception: Exception | None = None,
        url: str = "",
        payload: dict = {},
    ):
        super().__init__(message, detail, code)
        self.exception = exception
        self.url = url
        self.payload = payload
        self.log_message = f"❌ {message} : {self.exception}"

    @property
    def dict(self) -> dict:
        if self.exception:
            exception_dict = {
                "type": type(self.exception).__name__,
                "message": str(self.exception),
                "traceback": traceback.format_exc(),
                "attributes": {},
            }
            if (
                response := hasattr(self.exception, "response")
                and self.exception.response
            ):
                self.code = str(response.status_code) or ""

                try:
                    response_text = self.exception.response.text
                    exception_dict["response"] = json.loads(response_text)
                except json.JSONDecodeError:
                    pass
            for attr in dir(self.exception):
                try:
                    if (
                        not attr.startswith("__")
                        and not callable(attribute := getattr(self.exception, attr))
                        and getattr(self.exception, attr)
                    ):
                        try:
                            exception_dict["attributes"][attr] = json.loads(
                                str(attribute)
                            )
                        except json.JSONDecodeError:
                            pass
                except Exception:
                    pass

        result = {
            "message": self.message,
            "code": self.code,
            "url": self.url,
            "payload": self.payload,
            "detail": self.detail,
        }
        if self.exception:
            result["exception"] = exception_dict
        return result


def singleton(cls):
    """Decorator to create a singleton class
    Tested in tests/test_common.py
    """
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


def encrypt_value(value_to_encrypt: str, public_key: rsa.RSAPublicKey) -> str:
    """Encrypt the parameter value with the public key.

    Args:
        public_key (rsa.RSAPublicKey): The public key to encrypt with

    Returns:
        str: Base64 encoded encrypted value
    """
    if not value_to_encrypt:
        return None

    # Convert string to bytes and encrypt
    encrypted = public_key.encrypt(
        value_to_encrypt.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Return base64 encoded string for transmission
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_value(encrypted_value: str, private_key: rsa.RSAPrivateKey) -> str:
    """Decrypt an encrypted parameter value using the private key.

    Args:
        encrypted_value (str): Base64 encoded encrypted value
        private_key (rsa.RSAPrivateKey): The private key to decrypt with

    Returns:
        str: Decrypted value as string
    """
    if not encrypted_value:
        return None

    # Decode base64 string to bytes
    encrypted_bytes = base64.b64decode(encrypted_value)

    # Decrypt the value
    decrypted = private_key.decrypt(
        encrypted_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Return decoded string
    return decrypted.decode("utf-8")
