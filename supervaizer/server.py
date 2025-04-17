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
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import field_validator
from rich import inspect

from supervaizer.__version__ import API_VERSION, VERSION
from supervaizer.account import Account
from supervaizer.agent import Agent
from supervaizer.common import (
    ApiResult,
    ApiSuccess,
    SvBaseModel,
    decrypt_value,
    encrypt_value,
    log,
)
from supervaizer.instructions import display_instructions
from supervaizer.routes import (
    create_agents_routes,
    create_default_routes,
    create_utils_routes,
    get_server,
)
from supervaizer.protocol.a2a import create_routes as create_a2a_routes
from supervaizer.protocol.acp import create_routes as create_acp_routes

insp = inspect

T = TypeVar("T")


class ServerModel(SvBaseModel):
    """API Server for the Supervaize Controller."""

    model_config = {"arbitrary_types_allowed": True}  # for FastAPI
    supervaizer_VERSION: ClassVar[str] = VERSION
    scheme: str
    host: str
    port: int
    environment: str
    mac_addr: str
    debug: bool
    agents: List[Agent]
    app: FastAPI
    reload: bool
    supervisor_account: Optional[Account] = None
    a2a_endpoints: bool = True
    acp_endpoints: bool = True
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    registration_host: Optional[str] = None

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
        agents: List[Agent],
        supervisor_account: Optional[Account] = None,
        a2a_endpoints: bool = True,
        acp_endpoints: bool = True,
        scheme: str = "http",
        environment: str = os.getenv("SUPERVAIZER_ENVIRONMENT", "dev"),
        host: str = os.getenv("SUPERVAIZER_HOST", "0.0.0.0"),
        port: int = int(os.getenv("SUPERVAIZER_PORT", 8000)),
        debug: bool = False,
        reload: bool = False,
        mac_addr: str = "",
        private_key: Optional[RSAPrivateKey] = None,
        registration_host: Optional[str] = os.getenv(
            "SUPERVAIZER_REGISTRATION_HOST", None
        ),
        **kwargs: Any,
    ) -> None:
        """Initialize the server with the given configuration.

        Args:
            agents: List of agents to register with the server
            supervisor_account: Account of the supervisor
            a2a_endpoints: Whether to enable A2A endpoints
            acp_endpoints: Whether to enable ACP endpoints
            scheme: URL scheme (http or https)
            environment: Environment name (e.g., dev, staging, prod)
            host: Host to bind the server to (e.g., 0.0.0.0 for all interfaces)
            port: Port to bind the server to
            debug: Whether to enable debug mode
            reload: Whether to enable auto-reload
            mac_addr: MAC address to use for server identification
            private_key: RSA private key for encryption
            registration_host: Host to use for outbound connections and registration.
                This is especially important in Docker environments where the binding
                address (0.0.0.0) can't be used for outbound connections. Set to
                'host.docker.internal' for Docker or the appropriate service name
                in container environments.
                Examples:
                - In Docker, set to 'host.docker.internal' to reach the host machine
                - In Kubernetes, might be set to the service name or external DNS
                If not provided, falls back to using the listening host.

        """
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
            title="Supervaizer API",
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

        # Add exception handler for 422 validation errors
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(
            request: Request, exc: RequestValidationError
        ) -> JSONResponse:
            log.error(f"[422 Error] {exc.errors()}")
            return JSONResponse(
                status_code=422,
                content={"detail": exc.errors(), "body": exc.body},
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
            supervisor_account=supervisor_account,
            a2a_endpoints=a2a_endpoints,
            acp_endpoints=acp_endpoints,
            private_key=private_key,
            public_key=public_key,
            registration_host=registration_host,
            **kwargs,
        )

        # Create routes
        if self.supervisor_account:
            log.info("[Server launch] Deploy the supervision routes")
            self.app.include_router(create_default_routes(self))
            self.app.include_router(create_utils_routes(self))
            self.app.include_router(create_agents_routes(self))
        if self.a2a_endpoints:
            log.info("[Server launch] Deploy A2A routes")
            self.app.include_router(create_a2a_routes(self))
        if self.acp_endpoints:
            log.info("[Server launch] Deploy ACP routes")
            self.app.include_router(create_acp_routes(self))

        # Override the get_server dependency to return this instance
        async def get_current_server() -> "Server":
            return self

        # Update the dependency
        self.app.dependency_overrides[get_server] = get_current_server

    @property
    def url(self) -> str:
        """Get the server's base URL."""
        host = self.registration_host if self.registration_host else self.host
        return urlunparse((self.scheme, f"{host}:{self.port}", "", "", "", ""))

    @property
    def public_url(self) -> str:
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
            "public_key": str(
                self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("utf-8")
            ),
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

        log.info(
            f"[Server launch] Starting Supervaize Controller API v{VERSION} - Log : {log_level} "
        )

        # self.instructions()
        if self.supervisor_account:
            # Register the server with the supervisor account
            server_registration_result: ApiResult = (
                self.supervisor_account.register_server(server=self)
            )
            assert isinstance(
                server_registration_result, ApiSuccess
            )  # If ApiError, exception should have been raised before
            # Get the agent details from the server
            for agent in self.agents:
                updated_agent = agent.update_agent_from_server(self)
                if updated_agent:
                    log.info(f"[Server launch] Updated agent {updated_agent.name}")

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
