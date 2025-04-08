# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import base64
import json
import os
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar

import demjson3
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger
from pydantic import BaseModel, ConfigDict

log = logger.bind(module="supervaize")

T = TypeVar("T")


class SvBaseModel(BaseModel):
    """
    Base model for all Supervaize models.
    """

    model_config = ConfigDict(json_encoders={datetime: lambda x: x.isoformat()})

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @property
    def to_json(self) -> str:
        return self.model_dump_json()


class ApiResult:
    def __init__(self, message: str, detail: Optional[Dict[str, Any]], code: str):
        self.message = message
        self.code = str(code)
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.json_return}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.message})"

    @property
    def dict(self) -> Dict[str, Any]:
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

    def __init__(
        self, message: str, detail: Optional[Dict[str, Any] | str], code: int = 200
    ):
        if isinstance(detail, str):
            result = demjson3.decode(detail, return_errors=True)
            detail = {"object": result.object}
            id = result.object.get("id") or None
            log_message = f"✅ {message} : {id}" if id else f"✅ {message}"
        else:
            id = None
            detail = detail
            log_message = f"✅ {message}"

        super().__init__(
            message=message,
            detail=detail,
            code=str(code),
        )
        self.id: Optional[str] = id
        self.log_message = log_message


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
        detail: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        url: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, detail, code)
        self.exception = exception
        self.url = url
        self.payload = payload
        self.log_message = f"❌ {message} : {self.exception}"

    @property
    def dict(self) -> Dict[str, Any]:
        if self.exception:
            exception_dict: Dict[str, Any] = {
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

        result: Dict[str, Any] = {
            "message": self.message,
            "code": self.code,
            "url": self.url,
            "payload": self.payload,
            "detail": self.detail,
        }
        if self.exception:
            result["exception"] = exception_dict
        return result


def singleton(cls: type[T]) -> Callable[..., T]:
    """Decorator to create a singleton class
    Tested in tests/test_common.py
    """
    instances: Dict[type[T], T] = {}

    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


def encrypt_value(value_to_encrypt: str, public_key: rsa.RSAPublicKey) -> str:
    """Encrypt using hybrid RSA+AES encryption to handle messages of any size.

    Args:
        value_to_encrypt (str): Value to encrypt
        public_key (rsa.RSAPublicKey): RSA public key

    Returns:
        str: Base64 encoded encrypted value containing both the encrypted AES key and encrypted data

    Raises:
        ValueError: If encryption fails
    """

    # Generate random AES key and IV
    aes_key = os.urandom(32)  # 256-bit key
    iv = os.urandom(16)

    # Encrypt the AES key with RSA
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Create AES cipher
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()

    # Pad data to block size
    value_bytes = value_to_encrypt.encode("utf-8")
    pad_length = 16 - (len(value_bytes) % 16)
    value_bytes += bytes([pad_length]) * pad_length

    # Encrypt data with AES
    encrypted_data = encryptor.update(value_bytes) + encryptor.finalize()

    # Combine encrypted key, IV and data
    combined = encrypted_key + iv + encrypted_data

    # Return base64 encoded result
    return base64.b64encode(combined).decode("utf-8")


def decrypt_value(encrypted_value: str, private_key: rsa.RSAPrivateKey) -> str:
    """Decrypt using hybrid RSA+AES decryption.

    Args:
        encrypted_value (str): Base64 encoded encrypted value
        private_key (rsa.RSAPrivateKey): RSA private key

    Returns:
        str: Decrypted value as string

    Raises:
        ValueError: If decryption fails
    """

    # Decode base64
    combined = base64.b64decode(encrypted_value)

    # Extract components - first 256 bytes are RSA encrypted key
    encrypted_key = combined[:256]  # RSA-2048 output is 256 bytes
    iv = combined[256:272]  # 16 bytes IV
    encrypted_data = combined[272:]  # Rest is encrypted data

    # Decrypt AES key
    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # Create AES cipher
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor = cipher.decryptor()

    # Decrypt data
    decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()

    # Remove padding
    pad_length = decrypted_padded[-1]
    decrypted = decrypted_padded[:-pad_length]

    return decrypted.decode("utf-8")
