# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
import sys
import uuid
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)
from urllib.parse import urlunparse
from enum import Enum

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    status as http_status,
)
from fastapi.responses import JSONResponse
from pydantic import field_validator
from rich import inspect

from .__version__ import VERSION, API_VERSION
from .account import Account
from .agent import Agent, AgentCustomMethodParams, AgentMethodParams, AgentResponse
from .common import (
    ApiResult,
    ApiSuccess,
    SvBaseModel,
    decrypt_value,
    encrypt_value,
    log,
)
from .instructions import display_instructions
from .job import Job, JobContext, Jobs, JobStatus
from .parameter import Parameters
from .server_utils import ErrorResponse, ErrorType, create_error_response

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


default_router = APIRouter()


@default_router.get("/jobs/{job_id}", tags=["Jobs"], response_model=Job)
def get_job_status(job_id: str) -> Job:
    """Get the status of a job by its ID"""
    job = Jobs().get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    return job


@default_router.get("/jobs", tags=["Jobs"], response_model=Dict[str, List[Job]])
def get_all_jobs(
    skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Number of jobs to return"
    ),
    status: Optional[JobStatus] = Query(
        default=None, description="Filter jobs by status"
    ),
) -> Dict[str, List[Job]]:
    """Get all jobs across all agents with pagination and optional status filtering"""
    try:
        jobs_registry = Jobs()
        all_jobs: Dict[str, List[Job]] = {}

        for agent_name, agent_jobs in jobs_registry.jobs_by_agent.items():
            filtered_jobs = list(agent_jobs.values())

            # Apply status filter if specified
            if status:
                filtered_jobs = [job for job in filtered_jobs if job.status == status]

            # Apply pagination
            filtered_jobs = filtered_jobs[skip : skip + limit]

            if filtered_jobs:  # Only include agents that have jobs after filtering
                all_jobs[agent_name] = filtered_jobs

        return all_jobs
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def get_server() -> Optional["Server"]:
    """Dependency to get the current server instance"""
    # This will be replaced with the actual server instance at runtime
    # through the Server class's create_agent_routes method
    return None


@default_router.get("/agents", tags=["Agents"], response_model=List[AgentResponse])
async def get_all_agents(
    skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Number of jobs to return"
    ),
    server: Optional["Server"] = Depends(get_server),
) -> List[AgentResponse]:
    """Get all registered agents with pagination"""
    try:
        if not server:
            raise ValueError("Server instance not found")
        return [
            AgentResponse(**a.registration_info)
            for a in server.agents[skip : skip + limit]
        ]
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@default_router.get("/agent/{agent_id}", tags=["Agents"], response_model=AgentResponse)
async def get_agent_details(
    agent_id: str,
    server: Optional["Server"] = Depends(get_server),
) -> Union[Dict[str, Any], JSONResponse]:
    """Get details of a specific agent by ID"""
    try:
        if not server:
            raise ValueError("Server instance not found")
        for agent in server.agents:
            if agent.id == agent_id:
                return agent.registration_info

        return create_error_response(
            ErrorType.AGENT_NOT_FOUND,
            f"Agent with ID '{agent_id}' not found",
            http_status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return create_error_response(
            ErrorType.INTERNAL_ERROR,
            f"Failed to retrieve agent details: {str(e)}",
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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
        self.add_route(default_router)
        self.create_utils_routes()
        self.create_agent_routes()

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

    def add_route(self, route: APIRouter) -> None:
        """Add a route to the server."""
        self.app.include_router(route)

    def create_utils_routes(self) -> None:
        """Create utility routes."""
        router = APIRouter(prefix="/utils", tags=["Utils"])

        @router.get(
            "/public_key",
            summary="Get server's public key",
            description="Returns the server's public key in PEM format",
            response_model=str,
        )
        async def get_public_key() -> str:
            pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return pem.decode("utf-8")

        @router.post(
            "/encrypt",
            summary="Encrypt a string",
            description="Encrypts a string using the server's public key. Example: {'key':'value'}",
            response_model=str,
            response_description="The encrypted string",
        )
        async def encrypt_string(text: str = Body(...)) -> str:
            return self.encrypt(text)

        self.app.include_router(router)

    def create_agent_routes(self) -> None:
        """Create agent-specific routes."""
        for agent in self.agents:
            tags: list[str | Enum] = [f"Agent {agent.name} v{agent.version}"]
            router = APIRouter(
                prefix=agent.path,
                tags=tags,
            )

            async def get_agent() -> Agent:
                return agent

            @router.get(
                "/",
                summary=f"Get information about the agent {agent.name}",
                description="Detailed information about the agent, returned as a JSON object with Agent class fields",
                response_model=AgentResponse,
                responses={http_status.HTTP_200_OK: {"model": AgentResponse}},
                tags=tags,
            )
            async def agent_info(agent: Agent = Depends(get_agent)) -> AgentResponse:
                log.info(f"Getting agent info for {agent.name}")
                return AgentResponse(
                    name=agent.name,
                    id=agent.id,
                    version=agent.version,
                    api_path=agent.path,
                    description=agent.description,
                    **agent.registration_info,
                )

            @router.post(
                "/jobs",
                summary=f"Start a job with agent: {agent.name}",
                description=f"{agent.job_start_method.description}",
                responses={
                    http_status.HTTP_202_ACCEPTED: {"model": agent.job_start_method},
                    http_status.HTTP_409_CONFLICT: {"model": ErrorResponse},
                    http_status.HTTP_500_INTERNAL_SERVER_ERROR: {
                        "model": ErrorResponse
                    },
                },
                tags=tags,
                response_model=Job,
                status_code=http_status.HTTP_202_ACCEPTED,
            )
            async def start_job(
                background_tasks: BackgroundTasks,
                body_params: Any = Body(
                    ...
                ),  # Type will be validated by FastAPI at runtime
                agent: Agent = Depends(get_agent),
            ) -> Union[Job, JSONResponse]:
                """Start a new job for this agent"""
                try:
                    log.info(f"Starting agent {agent.name} with params {body_params}")
                    sv_context: JobContext = body_params.supervaize_context
                    job_fields = body_params.job_fields.to_dict()

                    # Get agent encrypted parameters if available
                    encrypted_agent_parameters = getattr(
                        body_params, "encrypted_agent_parameters", None
                    )
                    log.debug(
                        f"Encrypted agent parameters: {encrypted_agent_parameters}"
                    )

                    # If agent has parameters_setup defined, validate parameters
                    if agent.parameters_setup and encrypted_agent_parameters:
                        agent_parameters = Parameters.from_str(
                            self.decrypt(encrypted_agent_parameters)
                        )
                        log.debug(
                            f"Decrypted agent parameters: {agent_parameters}"
                        )  # TODO REMOVE ASAP

                    # Create and prepare the job
                    new_job = Job.new(
                        supervaize_context=sv_context,
                        agent_name=agent.name,
                        parameters=agent_parameters,
                    )

                    # Schedule the background execution
                    background_tasks.add_task(
                        agent.job_start, new_job, job_fields, sv_context
                    )

                    return new_job
                except ValueError as e:
                    if "already exists" in str(e):
                        return create_error_response(
                            ErrorType.JOB_ALREADY_EXISTS,
                            str(e),
                            http_status.HTTP_409_CONFLICT,
                        )
                    return create_error_response(
                        ErrorType.INVALID_REQUEST,
                        str(e),
                        http_status.HTTP_400_BAD_REQUEST,
                    )
                except Exception as e:
                    return create_error_response(
                        ErrorType.INTERNAL_ERROR,
                        str(e),
                        http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            @router.get(
                "/jobs",
                summary=f"Get all jobs for agent: {agent.name}",
                description="Get all jobs for this agent with pagination and optional status filtering",
                response_model=List[Job],
                responses={
                    http_status.HTTP_200_OK: {"model": List[Job]},
                    http_status.HTTP_500_INTERNAL_SERVER_ERROR: {
                        "model": ErrorResponse
                    },
                },
                tags=tags,
            )
            async def get_agent_jobs(
                agent: Agent = Depends(get_agent),
                skip: int = Query(
                    default=0, ge=0, description="Number of jobs to skip"
                ),
                limit: int = Query(
                    default=100, ge=1, le=1000, description="Number of jobs to return"
                ),
                status: JobStatus | None = Query(
                    default=None, description="Filter jobs by status"
                ),
            ) -> List[Job] | JSONResponse:
                """Get all jobs for this agent"""
                try:
                    jobs = list(Jobs().get_agent_jobs(agent.name).values())

                    # Apply status filter if specified
                    if status:
                        jobs = [job for job in jobs if job.status == status]

                    # Apply pagination
                    return jobs[skip : skip + limit]
                except ValueError as e:
                    return create_error_response(
                        ErrorType.INVALID_REQUEST,
                        str(e),
                        http_status.HTTP_400_BAD_REQUEST,
                    )
                except Exception as e:
                    return create_error_response(
                        ErrorType.INTERNAL_ERROR,
                        str(e),
                        http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            @router.get(
                "/jobs/{job_id}",
                summary=f"Get job status for agent: {agent.name}",
                description="Get the status and details of a specific job",
                response_model=Job,
                responses={
                    http_status.HTTP_200_OK: {"model": Job},
                    http_status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
                    http_status.HTTP_500_INTERNAL_SERVER_ERROR: {
                        "model": ErrorResponse
                    },
                },
                tags=tags,
            )
            async def get_job_status(
                job_id: str, agent: Agent = Depends(get_agent)
            ) -> Job:
                """Get the status of a job by its ID for this specific agent"""
                try:
                    job = Jobs().get_job(job_id, agent_name=agent.name)
                    if not job:
                        raise HTTPException(
                            status_code=http_status.HTTP_404_NOT_FOUND,
                            detail=f"Job with ID {job_id} not found for agent {agent.name}",
                        )
                    return job
                except ValueError as e:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=str(e),
                    )

            @router.post(
                "/stop",
                summary=f"Stop the agent: {agent.name}",
                description="Stop the agent",
                responses={
                    http_status.HTTP_202_ACCEPTED: {"model": AgentResponse},
                },
                tags=tags,
            )
            async def stop_agent(
                params: AgentMethodParams, agent: Agent = Depends(get_agent)
            ) -> AgentResponse:
                log.info(f"Stopping agent {agent.name} with params {params}")
                result = agent.job_stop(params.dict())
                return AgentResponse(
                    name=agent.name,
                    id=agent.id,
                    version=agent.version,
                    api_path=agent.path,
                    description=agent.description,
                    **result if result else {},
                )

            @router.post(
                "/status",
                summary=f"Get the status of the agent: {agent.name}",
                description="Get the status of the agent",
                responses={
                    http_status.HTTP_202_ACCEPTED: {"model": AgentResponse},
                },
                tags=tags,
            )
            async def status_agent(
                params: AgentMethodParams, agent: Agent = Depends(get_agent)
            ) -> AgentResponse:
                log.info(f"Getting status of agent {agent.name} with params {params}")
                result = agent.job_status(params.dict())
                return AgentResponse(
                    name=agent.name,
                    id=agent.id,
                    version=agent.version,
                    api_path=agent.path,
                    description=agent.description,
                    **result if result else {},
                )

            @router.post(
                "/custom",
                summary=f"Trigger a custom method for agent: {agent.name}",
                description="Trigger a custom method",
                response_model=AgentResponse,
                responses={
                    http_status.HTTP_202_ACCEPTED: {"model": AgentResponse},
                    http_status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse},
                },
                tags=tags,
            )
            async def custom_method(
                params: AgentCustomMethodParams, agent: Agent = Depends(get_agent)
            ) -> AgentResponse:
                log.info(
                    f"Triggering custom method {params.method_name} for agent {agent.name} with params {params.params}"
                )
                if agent.custom_methods and params.method_name in agent.custom_methods:
                    method = agent.custom_methods[params.method_name]
                    if callable(method):
                        result = method(params.params)
                    else:
                        result = method
                    return AgentResponse(
                        name=agent.name,
                        id=agent.id,
                        version=agent.version,
                        api_path=agent.path,
                        description=agent.description,
                        **result if result else {},
                    )
                else:
                    raise HTTPException(
                        status_code=http_status.HTTP_405_METHOD_NOT_ALLOWED,
                        detail="Custom method not found",
                    )

            self.app.include_router(router)

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
