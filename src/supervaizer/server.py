# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import os
import secrets
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any, ClassVar, TypeVar, cast
from urllib.parse import urlunparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import FastAPI, HTTPException, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse  # <-- MODIFIED: removed unused HTMLResponse
from fastapi.security import APIKeyHeader

# <-- REMOVED: Jinja2Templates (home page moved to routers/public.py)
from pydantic import ConfigDict, Field, field_validator
from rich import inspect

from supervaizer.__version__ import VERSION
from supervaizer.account import Account
from supervaizer.agent import (
    Agent,
)  # <-- MODIFIED: removed AdminIPAllowlistMiddleware, create_admin_routes imports
from supervaizer.common import (
    ApiResult,
    ApiSuccess,
    SvBaseModel,
    configure_controller_logging,
    decrypt_value,
    encrypt_value,
    is_local_mode,
    log,
)
from supervaizer.contracts import (
    API_VERSION,
    V2WorkspaceAuthorizationSettings,
)
from supervaizer.instructions import display_instructions
from supervaizer.protocol.a2a.controller import (
    ActionHandler,
    SurfaceHandler,
    register_v2_action_handler,
    register_v2_surface_handler,
)
from supervaizer.routers import (
    create_api_router,
    create_private_router,
    create_public_router,
)  # <-- ADDED
from supervaizer.routes import get_server  # <-- MODIFIED: removed per-router imports
from supervaizer.scheduled_steps import (
    _execute_scheduled_method as _execute_scheduled_method,
    _run_scheduled_step_loop,
)
from supervaizer.server_config import (
    _controller_key_fingerprint,
    _env_bool as _env_bool,
    _get_or_create_private_key,
    _get_or_create_server_id,
    _resolve_workspace_authorization_settings,
)
from supervaizer.server_info import (
    ServerInfo as ServerInfo,
    get_server_info_from_live as get_server_info_from_live,
    get_server_info_from_storage as get_server_info_from_storage,
    save_server_info_to_storage,
)
from supervaizer.server_registration import build_server_registration_info
from supervaizer.storage import load_running_entities_on_startup
from supervaizer.studio_handshake import (
    apply_workspace_authorization_agent_bindings,
    apply_workspace_authorization_handshake,
    validate_registration_handshake,
    validate_studio_a2a_workspace_authorization,
)
from supervaizer.workspace_authorization import (
    validate_workspace_authorization_settings,
)

insp = inspect

T = TypeVar("T")
SCHEDULED_STEP_SHUTDOWN_TIMEOUT_SECONDS = 5.0


def _agent_v2_method_handler(agent: Agent, action: str) -> ActionHandler:
    def handler(request: Any) -> Any:
        return agent.execute_v2_action_method(action, request)

    return handler


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
    server_id: str = Field(
        default_factory=_get_or_create_server_id,
        description="Unique server id (SUPERVAIZER_SERVER_ID env or persisted uuid)",
    )
    scheme: str = Field(description="URL scheme (http or https)")
    host: str = Field(
        description="Host to bind the server to (e.g., 0.0.0.0 for all interfaces)"
    )
    port: int = Field(description="Port to bind the server to")
    environment: str = Field(description="Environment name (e.g., dev, staging, prod)")
    mac_addr: str = Field(description="MAC address to use for server identification")
    debug: bool = Field(description="Whether to enable debug mode")
    agents: list[Agent] = Field(
        description="List of agents to register with the server"
    )
    app: FastAPI = Field(description="FastAPI application instance")
    reload: bool = Field(description="Whether to enable auto-reload")
    supervisor_account: Account | None = Field(
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
    public_url: str | None = Field(
        default=None,
        description="Public including scheme and port to use for inbound connections",
    )
    api_key: str | None = Field(
        default=None,
        description="Force the API key to access the supervaizer endpoints - if not provided, a random key will be generated",
    )
    api_key_header: APIKeyHeader | None = Field(
        default=None, description="API key header for authentication"
    )
    workspace_authorization: V2WorkspaceAuthorizationSettings = Field(
        default_factory=V2WorkspaceAuthorizationSettings,
        description="Optional Studio-signed workspace authorization verifier settings",
    )

    model_config = cast(
        ConfigDict,
        {
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
        },
    )

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

    def get_agent_by_name(self, agent_name: str) -> Agent | None:
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        return None


class Server(ServerAbstract):
    def __init__(
        self,
        agents: list[Agent],
        supervisor_account: Account | None = None,
        a2a_endpoints: bool = True,
        admin_interface: bool = True,
        scheme: str = "http",
        environment: str | None = None,
        host: str | None = None,
        port: int | None = None,
        debug: bool = False,
        reload: bool = False,
        mac_addr: str = "",
        private_key: RSAPrivateKey | None = None,
        public_url: str | None = None,
        api_key: str | None = None,
        workspace_authorization: V2WorkspaceAuthorizationSettings
        | dict[str, Any]
        | None = None,
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
        # Resolve defaults from env vars at call time (not class definition time).
        # This ensures CLI-set env vars are picked up even when the module was
        # imported before the CLI ran.
        if environment is None:
            environment = os.getenv("SUPERVAIZER_ENVIRONMENT", "dev")
        if host is None:
            host = os.getenv("SUPERVAIZER_HOST", "0.0.0.0")
        if port is None:
            port = int(os.getenv("SUPERVAIZER_PORT", "8000"))
        if public_url is None:
            public_url = os.getenv("SUPERVAIZER_PUBLIC_URL") or None
        local_mode = is_local_mode()
        api_key_was_generated = False
        if api_key is None:
            api_key = os.getenv("SUPERVAIZER_API_KEY")
            if not api_key:
                if local_mode:
                    api_key = "local-dev"
                else:
                    api_key = secrets.token_urlsafe(32)
                    os.environ["SUPERVAIZER_API_KEY"] = api_key
                    api_key_was_generated = True

        # Local mode: skip Studio, inject Hello World, default api_key
        local_hello_world_slug: str | None = None
        if local_mode:
            if supervisor_account is not None:
                log.warning(
                    "[Server] Local mode active — ignoring supervisor_account"
                    " (no Studio registration)"
                )
            supervisor_account = None
            a2a_endpoints = True
            admin_interface = True

            # Inject Hello World agent unless disabled or duplicate
            if os.environ.get("SUPERVAIZER_DISABLE_HELLO_WORLD", "").lower() != "true":
                from supervaizer.examples.local_server import (
                    get_default_local_agent,
                )

                hw_agent = get_default_local_agent()
                existing_slugs = {a.slug for a in agents}
                if hw_agent.slug not in existing_slugs:
                    agents = [hw_agent] + list(agents)
                    local_hello_world_slug = hw_agent.slug
            elif not agents:
                log.warning(
                    "[Server] Local mode with Hello World disabled and no"
                    " agents — server will be empty"
                )

        if not mac_addr:
            node_id = uuid.getnode()
            mac_addr = "-".join(
                format(node_id, "012X")[i : i + 2] for i in range(0, 12, 2)
            )

        if private_key is None:
            private_key = _get_or_create_private_key()
        workspace_authorization_settings = _resolve_workspace_authorization_settings(
            workspace_authorization
        )
        validate_workspace_authorization_settings(workspace_authorization_settings)

        public_key = private_key.public_key()
        log.info(f"[Server launch] Public key: {public_key}")
        log.info(
            f"[Server launch] Public key - decode:  {
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode('utf-8')!s
            },"
        )
        # Create root app to handle version prefix
        docs_url = "/docs"  # Swagger UI
        redoc_url = "/redoc"  # ReDoc
        openapi_url = "/openapi.json"

        @asynccontextmanager
        async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
            # Keep a task handle so shutdown can stop the scheduler cleanly.
            scheduled_step_task = asyncio.create_task(
                _run_scheduled_step_loop(self),
                name="supervaizer-scheduled-step-loop",
            )
            try:
                yield
            finally:
                # Give the scheduler a bounded chance to observe cancellation.
                scheduled_step_task.cancel()
                done, pending = await asyncio.wait(
                    {scheduled_step_task},
                    timeout=SCHEDULED_STEP_SHUTDOWN_TIMEOUT_SECONDS,
                )
                if pending:
                    log.warning(
                        "[Scheduled step] Shutdown timed out while waiting for "
                        "the scheduler task to stop"
                    )
                if done:
                    with suppress(asyncio.CancelledError):
                        await scheduled_step_task

        app = FastAPI(
            lifespan=_lifespan,
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
            workspace_authorization=workspace_authorization_settings,
            **kwargs,
        )

        if local_hello_world_slug:
            from supervaizer.examples.local_server import (
                register_default_local_v2_handlers,
            )

            register_default_local_v2_handlers(
                self,
                agent_slug=local_hello_world_slug,
            )

        log.info(f"[Server launch] Server ID: {self.server_id}")

        # Store server instance on app state before building routers
        self.app.state.server = self  # <-- MOVED earlier (was after route mount)
        self._register_agent_v2_method_handlers()

        # Activate API + A2A routes when supervisor account or local mode is set
        if self.supervisor_account or local_mode:
            log.info(
                "[Server launch] 🚀 Deploy API routes (/api)"
                + (" (local mode)" if local_mode else "")
            )
            self.a2a_endpoints = True
            self.app.include_router(create_api_router(self))  # <-- ADDED: /api surface

        # Public surface: home page + A2A discovery  # <-- ADDED
        self.app.include_router(
            create_public_router(self, admin_interface=admin_interface)
        )
        log.info("[Server launch] 🌐 Deploy public routes (/)")

        # Private surface: admin UI + workbench (Tailscale-only)  # <-- ADDED
        if self.api_key and admin_interface:
            log.info(
                f"[Server launch] 💼 Deploy admin interface @ {self.public_url}/manage"
            )
            self.app.include_router(
                create_private_router()
            )  # <-- ADDED: /manage surface
            # <-- REMOVED: AdminIPAllowlistMiddleware (replaced by require_tailscale)
            # <-- REMOVED: create_admin_routes() prefix="/admin" (now inside private_router)

            # Save server info to storage for admin interface
            save_server_info_to_storage(self)
        # <-- REMOVED: inline home_page handler (moved to routers/public.py)

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

        # Expose live server for admin when storage has no ServerInfo (e.g. no persistence)
        self._start_time = time.time()
        self.app.state.server = self

        if api_key:
            log.info("[Server launch] API Key authentication enabled")
            # Print the API key if it was generated
            if api_key_was_generated:
                log.warning(
                    "[Server launch] Using auto-generated API key "
                    f"fingerprint={_controller_key_fingerprint(api_key)}"
                )
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
    def registration_info(self) -> dict[str, Any]:
        """Get registration info for the server."""
        return build_server_registration_info(self)

    def launch(self, log_level: str | None = "INFO") -> None:
        if log_level:
            configure_controller_logging(log_level)

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

        self._validate_studio_a2a_workspace_authorization()

        # self.instructions()
        if self.supervisor_account:
            # Register the server with the supervisor account
            server_registration_result: ApiResult = (
                self.supervisor_account.register_server_sync(server=self)
            )
            # log.debug(f"[Server launch] Server registration result: {server_registration_result}")
            # inspect(server_registration_result)
            assert isinstance(
                server_registration_result, ApiSuccess
            )  # If ApiError, exception should have been raised before
            self._validate_registration_handshake(server_registration_result)
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

    def _validate_registration_handshake(self, result: ApiSuccess) -> None:
        validate_registration_handshake(self, result)

    def _validate_studio_a2a_workspace_authorization(self) -> None:
        validate_studio_a2a_workspace_authorization(self)

    def _apply_workspace_authorization_handshake(
        self, handshake: dict[str, Any]
    ) -> None:
        apply_workspace_authorization_handshake(self, handshake)

    def _apply_workspace_authorization_agent_bindings(
        self, agent_bindings: list[Any]
    ) -> None:
        apply_workspace_authorization_agent_bindings(self, agent_bindings)

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

    def register_v2_action(
        self, action: str, handler: ActionHandler, *, agent_slug: str | None = None
    ) -> ActionHandler:
        """Register a Supervaizer v2 action handler on this server."""
        register_v2_action_handler(self, action, handler, agent_slug=agent_slug)
        return handler

    def _register_agent_v2_method_handlers(self) -> None:
        for agent in self.agents:
            for action in agent.v2_action_ids:
                self.register_v2_action(
                    action,
                    _agent_v2_method_handler(agent, action),
                    agent_slug=agent.slug,
                )

    def v2_action(
        self, action: str, *, agent_slug: str | None = None
    ) -> Callable[[ActionHandler], ActionHandler]:
        """Decorator form of register_v2_action for SDK users."""

        def decorator(handler: ActionHandler) -> ActionHandler:
            return self.register_v2_action(action, handler, agent_slug=agent_slug)

        return decorator

    def register_v2_surface(
        self, surface: str, handler: SurfaceHandler, *, agent_slug: str | None = None
    ) -> SurfaceHandler:
        """Register a Supervaizer v2 A2UI surface handler on this server."""
        register_v2_surface_handler(self, surface, handler, agent_slug=agent_slug)
        return handler

    def v2_surface(
        self, surface: str, *, agent_slug: str | None = None
    ) -> Callable[[SurfaceHandler], SurfaceHandler]:
        """Decorator form of register_v2_surface for SDK users."""

        def decorator(handler: SurfaceHandler) -> SurfaceHandler:
            return self.register_v2_surface(surface, handler, agent_slug=agent_slug)

        return decorator
