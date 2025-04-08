# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
import sys
import uuid
from typing import Any, ClassVar, Dict, List, Optional, TypeVar
from urllib.parse import urlunparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import FastAPI
from pydantic import field_validator
from rich import inspect

from .__version__ import VERSION, API_VERSION
from .account import Account
from .agent import Agent
from .common import (
    ApiResult,
    ApiSuccess,
    SvBaseModel,
    decrypt_value,
    encrypt_value,
    log,
)
from .instructions import display_instructions
from .routes import (
    create_default_routes,
    create_utils_routes,
    create_agents_routes,
    get_server,
)

insp = inspect

T = TypeVar("T")


class ServerModel(SvBaseModel):
    """API Server for the Supervaize Control."""

    model_config = {"arbitrary_types_allowed": True}  # for FastAPI
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    scheme: str
    host: str
    port: int
    environment: str
    mac_addr: str
    debug: bool
    agents: List[Agent]
    app: FastAPI
    reload: bool
    account: Account
    private_key: RSAPrivateKey
    public_key: RSAPublicKey

    @field_validator("scheme")
    def scheme_validator(cls, v: str) -> str:
        if "://" in v:
            raise ValueError(f"Scheme should not include '://': {v}")
        return v

    @field_validator("host")
    def host_validator(cls, v: str) -> str:
        if "://" in v:
            raise ValueError(f"Host should not include '://': {v}")
        return v

    def get_agent_by_name(self, agent_name: str) -> Optional[Agent]:
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        return None


class Server(ServerModel):
    def __init__(
        self,
        account: Account,
        agents: List[Agent],
        scheme: str = "http",
        environment: str = os.getenv("SUPERVAIZE_CONTROL_ENVIRONMENT", "dev"),
        host: str = os.getenv("SUPERVAIZE_CONTROL_HOST", "0.0.0.0"),
        port: int = int(os.getenv("SUPERVAIZE_CONTROL_PORT", 8001)),
        debug: bool = False,
        reload: bool = False,
        mac_addr: str = "",
        private_key: Optional[RSAPrivateKey] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the server with the given configuration."""
        if not mac_addr:
            node_id = uuid.getnode()
            mac_addr = "-".join(
                format(node_id, "012X")[i : i + 2] for i in range(0, 12, 2)
            )

        if private_key is None:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )

        public_key = private_key.public_key()

        # Create root app to handle version prefix
        docs_url = "/docs"  # Swagger UI
        redoc_url = "/redoc"  # ReDoc
        openapi_url = "/openapi.json"

        app = FastAPI(
            debug=debug,
            title="Supervaize Control API",
            description=(
                f"API version: {API_VERSION}  Controller version: {VERSION}\n\n"
                "API for controlling and managing Supervaize agents. \n\nMore information at "
                "[https://supervaize.com/docs/integration](https://supervaize.com/docs/integration)\n\n\n\n"
                f"[Swagger]({docs_url})\n"
                f"[Redoc]({redoc_url})\n"
                f"[OpenAPI]({openapi_url})\n"
            ),
            version=API_VERSION,
            terms_of_service="https://supervaize.com/terms/",
            contact={
                "name": "Support Team",
                "url": "https://supervaize.com/dev_contact/",
                "email": "integration_support@supervaize.com",
            },
            license_info={
                "name": "Mozilla Public License 2.0",
                "url": "https://mozilla.org/MPL/2.0/",
            },
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
        )

        super().__init__(
            scheme=scheme,
            host=host,
            port=port,
            environment=environment,
            mac_addr=mac_addr,
            debug=debug,
            agents=agents,
            app=app,
            reload=reload,
            account=account,
            private_key=private_key,
            public_key=public_key,
            **kwargs,
        )

        # Create routes
        self.app.include_router(create_default_routes(self))
        self.app.include_router(create_utils_routes(self))
        self.app.include_router(create_agents_routes(self))

        # Override the get_server dependency to return this instance
        async def get_current_server() -> "Server":
            return self

        # Update the dependency
        self.app.dependency_overrides[get_server] = get_current_server

    @property
    def url(self) -> str:
        """Get the server's base URL."""
        return urlunparse((self.scheme, f"{self.host}:{self.port}", "", "", "", ""))

    @property
    def uri(self) -> str:
        """Get the server's URI."""
        return f"server:{self.mac_addr}"

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Get registration info for the server."""
        assert self.public_key is not None, "Public key not initialized"
        return {
            "url": self.url,
            "uri": self.uri,
            "api_version": API_VERSION,
            "environment": self.environment,
            "public_key": self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8"),
            "docs": {
                "swagger": f"{self.url}{self.app.docs_url}",
                "redoc": f"{self.url}{self.app.redoc_url}",
                "openapi": f"{self.url}{self.app.openapi_url}",
            },
            "agents": [agent.registration_info for agent in self.agents],
        }

    def launch(self, log_level: Optional[str] = "INFO") -> None:
        log.remove()
        if log_level:
            log.add(
                sys.stderr,
                colorize=True,
                format="<green>{time}</green>|<level> {level}</level> | <level>{message}</level>",
                level=log_level,
            )
            log_level = (
                log_level.lower()
            )  # needs to be lower case of uvicorn and uppercase of loguru

        log.info(f"Starting Supervaize Control API v{VERSION} - Log : {log_level} ")

        # self.instructions()

        server_registration_result: ApiResult = self.account.register_server(
            server=self
        )
        assert isinstance(
            server_registration_result, ApiSuccess
        )  # If ApiError, exception should have been raised before

        for agent in self.agents:
            updated_agent = agent.update_agent_from_server(self)
            if updated_agent:
                log.info(f"Updated agent {updated_agent.name}")
        import uvicorn

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            reload=self.reload,
            log_level=log_level,
        )

    def instructions(self) -> None:
        server_url = f"http://{self.host}:{self.port}"
        display_instructions(
            server_url, f"Starting server on {server_url} \n Waiting for instructions.."
        )

    def decrypt(self, encrypted_parameters: str) -> str:
        """Decrypt parameters using the server's private key."""
        result = decrypt_value(encrypted_parameters, self.private_key)
        if result is None:
            raise ValueError("Failed to decrypt parameters")
        return result

    def encrypt(self, parameters: str) -> str:
        """Encrypt parameters using the server's public key."""
        result = encrypt_value(parameters, self.public_key)
        if result is None:
            raise ValueError("Failed to encrypt parameters")
        return result
