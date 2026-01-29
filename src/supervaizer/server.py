# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
import secrets
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, TypeVar
from urllib.parse import urlunparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import FastAPI, HTTPException, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator, Field
from rich import inspect

from supervaizer.__version__ import API_VERSION, VERSION
from supervaizer.account import Account
from supervaizer.admin.routes import create_admin_routes
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
from supervaizer.protocol.a2a import create_routes as create_a2a_routes
from supervaizer.routes import (
    create_agents_routes,
    create_default_routes,
    create_utils_routes,
    get_server,
)
from supervaizer.storage import (
    PERSISTENCE_ENABLED,
    StorageManager,
    load_running_entities_on_startup,
)

insp = inspect

T = TypeVar("T")

# Additional imports for server persistence


class ServerInfo(BaseModel):
    """Complete server information for storage."""

    id: str = "server_instance"  # Fixed ID for singleton
    host: str
    port: int
    api_version: str
    environment: str
    agents: List[Dict[str, str]]
    start_time: float
    created_at: str
    updated_at: str


def save_server_info_to_storage(server_instance: "Server") -> None:
    """Save server information to storage (only when persistence is enabled)."""
    if not PERSISTENCE_ENABLED:
        return
    try:
        storage = StorageManager()

        # Get agent information
        agents = []
        if hasattr(server_instance, "agents") and server_instance.agents:
            for agent in server_instance.agents:
                agents.append({
                    "name": agent.name,
                    "description": agent.description,
                    "version": agent.version,
                    "api_path": agent.path,
                    "slug": agent.slug,
                    "instructions_path": agent.instructions_path,
                })

        # Create server info
        server_info = ServerInfo(
            host=getattr(server_instance, "host", "N/A"),
            port=getattr(server_instance, "port", "N/A"),
            api_version=API_VERSION,
            environment=os.getenv("SUPERVAIZER_ENVIRONMENT", "development"),
            agents=agents,
            start_time=time.time(),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        # Save to storage
        storage.save_object("ServerInfo", server_info.model_dump())

        log.info(
            f"[Server] Server info saved to storage: {server_info.host}:{server_info.port}"
        )

    except Exception as e:
        log.error(f"[Server] Failed to save server info to storage: {e}")


def get_server_info_from_storage() -> Optional[ServerInfo]:
    """Get server information from storage."""
    storage = StorageManager()
    server_data = storage.get_object_by_id("ServerInfo", "server_instance")

    if server_data:
        return ServerInfo.model_validate(server_data)
    return None


class ServerAbstract(SvBaseModel):
    """
    API Server for the Supervaize Controller.

    The server is a FastAPI application (see https://fastapi.tiangolo.com/ for details and advanced parameters)

    This represents the main server instance that manages agents and provides
    the API endpoints for the Supervaize Control API. It handles agent registration,
    job execution, and communication with the Supervaize platform.

    The server can be configured with various endpoints (A2A, ACP, admin interface)
    and supports encryption/decryption of parameters using RSA keys.

    Note that when the supervisor ccount is set, the A2A protocol is automatically activated to provide HEALTH CHECK endpoints.

    public_url: full url (including scheme and port) to use for outbound connections and registration.
                This is especially important in Docker environments where the binding
                address (0.0.0.0) can't be used for outbound connections. Set to
                'host.docker.internal' for Docker or the appropriate service name
                in container environments.
                Examples:
                - In Docker, set to 'http://host.docker.internal' to reach the host machine
                - In Kubernetes, might be set to the service name or external DNS
                If not provided, falls back to using the listening host.

    """

    supervaizer_VERSION: ClassVar[str] = VERSION
    scheme: str = Field(description="URL scheme (http or https)")
    host: str = Field(
        description="Host to bind the server to (e.g., 0.0.0.0 for all interfaces)"
    )
    port: int = Field(description="Port to bind the server to")
    environment: str = Field(description="Environment name (e.g., dev, staging, prod)")
    mac_addr: str = Field(description="MAC address to use for server identification")
    debug: bool = Field(description="Whether to enable debug mode")
    agents: List[Agent] = Field(
        description="List of agents to register with the server"
    )
    app: FastAPI = Field(description="FastAPI application instance")
    reload: bool = Field(description="Whether to enable auto-reload")
    supervisor_account: Optional[Account] = Field(
        default=None,
        description="Account of the supervisor - can be created at supervaize.com",
    )
    a2a_endpoints: bool = Field(
        default=True, description="Whether to enable A2A endpoints"
    )
    private_key: RSAPrivateKey = Field(
        description="RSA private key for secret parameters encryption - Used in server-to-agent communication - Not needed by user"
    )
    public_key: RSAPublicKey = Field(
        description="RSA public key for secret parameters encryption - Used in agent-to-server communication - Not needed by user"
    )
    public_url: Optional[str] = Field(
        default=None,
        description="Public including scheme and port to use for inbound connections",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Force the API key to access the supervaizer endpoints - if not provided, a random key will be generated",
    )
    api_key_header: Optional[APIKeyHeader] = Field(
        default=None, description="API key header for authentication"
    )

    model_config = {
        "reference_group": "Core",
        "arbitrary_types_allowed": True,  # for FastAPI
        "json_schema_extra": {
            "examples": [
                {
                    "agents": "[agent]",
                    "a2a_enabled": True,
                    "supervisor_account": None,
                },
                {
                    "scheme": "http",
                    "host": "0.0.0.0",
                    "port": 8000,
                    "environment": "dev",
                    "mac_addr": "00-11-22-33-44-55",
                    "debug": False,
                    "reload": False,
                    "a2a_endpoints": True,
                },
            ]
        },
    }

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


class Server(ServerAbstract):
    def __init__(
        self,
        agents: List[Agent],
        supervisor_account: Optional[Account] = None,
        a2a_endpoints: bool = True,
        admin_interface: bool = True,
        scheme: str = os.getenv("SUPERVAIZER_SCHEME", "https"),
        environment: str = os.getenv("SUPERVAIZER_ENVIRONMENT", "dev"),
        host: str = os.getenv("SUPERVAIZER_HOST", "0.0.0.0"),
        port: int = int(os.getenv("SUPERVAIZER_PORT", 443)),
        debug: bool = False,
        reload: bool = False,
        mac_addr: str = "",
        private_key: Optional[RSAPrivateKey] = None,
        public_url: Optional[str] = os.getenv("SUPERVAIZER_PUBLIC_URL", None),
        api_key: Optional[str] = os.getenv(
            "SUPERVAIZER_API_KEY", secrets.token_urlsafe(32)
        ),
        **kwargs: Any,
    ) -> None:
        """Initialize the server with the given configuration.

        Args:
            agents: List of agents to register with the server
            supervisor_account: Account of the supervisor
            a2a_endpoints: Whether to enable A2A endpoints
            admin_interface: Whether to enable admin interface
            scheme: URL scheme (http or https)
            environment: Environment name (e.g., dev, staging, prod)
            host: Host to bind the server to (e.g., 0.0.0.0 for all interfaces)
            port: Port to bind the server to
            debug: Whether to enable debug mode
            reload: Whether to enable auto-reload
            mac_addr: MAC address to use for server identification
            private_key: RSA private key for encryption

            api_key: API key for securing endpoints

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
                "[https://doc.supervaize.com](https://doc.supervaize.com)\n\n"
                "## Authentication\n\n"
                "Some endpoints require API key authentication. Protected endpoints expect "
                "the API key in the X-API-Key header.\n\n"
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

        # Create API key header security
        API_KEY_NAME = "X-API-Key"
        api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

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
            private_key=private_key,
            public_key=public_key,
            public_url=public_url,
            api_key=api_key,
            api_key_header=api_key_header,
            **kwargs,
        )

        # Create routes
        if self.supervisor_account:
            log.info(
                "[Server launch] 🚀 Deploy Supervaizer routes - also activates A2A routes"
            )
            self.app.include_router(create_default_routes(self))
            self.app.include_router(create_utils_routes(self))
            self.app.include_router(create_agents_routes(self))
            self.a2a_endpoints = True  # Needed by supervaize.
        if self.a2a_endpoints:
            log.info("[Server launch] 📢 Deploy A2A routes  ")
            self.app.include_router(create_a2a_routes(self))

        # Deploy admin routes if API key is available
        if self.api_key and admin_interface:
            log.info(
                f"[Server launch] 💼 Deploy Admin interface @ {self.public_url}/admin"
            )
            self.app.include_router(create_admin_routes(), prefix="/admin")

            # Save server info to storage for admin interface
            save_server_info_to_storage(self)

        # Favicon (served at root so /docs, /redoc, etc. pick it up)
        _favicon_path = Path(__file__).parent / "admin" / "static" / "favicon.ico"

        @self.app.get("/favicon.ico", include_in_schema=False)
        async def favicon() -> FileResponse:
            return FileResponse(_favicon_path, media_type="image/x-icon")

        # Home page (template in admin/templates)
        _home_templates = Jinja2Templates(
            directory=str(Path(__file__).parent / "admin" / "templates")
        )

        @self.app.get("/", response_class=HTMLResponse)
        async def home_page(request: Request) -> HTMLResponse:
            root_index = Path.cwd() / "index.html"
            if root_index.is_file():
                return HTMLResponse(content=root_index.read_text(encoding="utf-8"))
            base = self.public_url or f"{self.scheme}://{self.host}:{self.port}"
            return _home_templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "base": base,
                    "public_url": self.public_url,
                    "full_url": f"{self.scheme}://{self.host}:{self.port}",
                    "version": VERSION,
                    "api_version": API_VERSION,
                    "show_admin": bool(self.api_key and admin_interface),
                },
            )

        # Load running entities from storage into memory
        try:
            load_running_entities_on_startup()
        except Exception as e:
            log.error(f"[Server launch] Failed to load running entities: {e}")
            raise

        # Override the get_server dependency to return this instance
        async def get_current_server() -> "Server":
            return self

        # Update the dependency
        self.app.dependency_overrides[get_server] = get_current_server

        if api_key:
            log.info("[Server launch] API Key authentication enabled")
            # Print the API key if it was generated
            if os.getenv("SUPERVAIZER_API_KEY") is None:
                log.warning(f"[Server launch] Using auto-generated API key: {api_key}")
        else:
            log.info("[Server launch] API Key authentication disabled")

        if not self.public_url:
            self.public_url = f"{self.scheme}://{self.host}:{self.port}"

    async def verify_api_key(
        self, api_key: str = Security(APIKeyHeader(name="X-API-Key"))
    ) -> bool:
        """Verify that the API key is valid.

        Args:
            api_key: The API key from the request header

        Returns:
            True if the API key is valid

        Raises:
            HTTPException: If the API key is invalid or not provided when required
        """
        if self.api_key is None:
            # API key authentication is disabled
            return True

        if api_key != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "APIKey"},
            )

        return True

    @property
    def url(self) -> str:
        """Get the server's local URL."""
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
            "url": self.public_url,
            "uri": self.uri,
            "api_version": API_VERSION,
            "environment": self.environment,
            "public_key": str(
                self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("utf-8")
            ),
            "api_key": self.api_key,
            "docs": {
                "swagger": f"{self.public_url}{self.app.docs_url}",
                "redoc": f"{self.public_url}{self.app.redoc_url}",
                "openapi": f"{self.public_url}{self.app.openapi_url}",
            },
            "agents": [agent.registration_info for agent in self.agents],
        }

    def launch(
        self, log_level: Optional[str] = "INFO", start_uvicorn: bool = False
    ) -> None:
        if log_level:
            log.remove()
            log.add(
                sys.stderr,
                colorize=True,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>|<level> {level}</level> | <level>{message}</level>",
                level=log_level,
            )

            # Add log handler for admin streaming if API key is enabled
            if self.api_key:

                def log_queue_handler(message: Any) -> None:
                    record = message.record
                    try:
                        # Import here to avoid circular imports and ensure module is loaded
                        import supervaizer.admin.routes as admin_routes

                        admin_routes.add_log_to_queue(
                            timestamp=record["time"].isoformat(),
                            level=record["level"].name,
                            message=record["message"],
                        )
                    except ImportError:
                        # Silently ignore import errors to avoid breaking logging
                        pass
                    except Exception:
                        # Silently ignore other errors to avoid breaking logging
                        pass

                # Add the handler with a specific format to avoid recursion
                log.add(log_queue_handler, level=log_level, format="{message}")

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
            # log.debug(f"[Server launch] Server registration result: {server_registration_result}")
            # inspect(server_registration_result)
            assert isinstance(
                server_registration_result, ApiSuccess
            )  # If ApiError, exception should have been raised before
            # Get the agent details from the server
            for agent in self.agents:
                updated_agent = agent.update_agent_from_server(self)
                if updated_agent:
                    log.info(f"[Server launch] Updated agent {updated_agent.name}")

        if start_uvicorn:
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
