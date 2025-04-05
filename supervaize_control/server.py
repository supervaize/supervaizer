# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import uuid
from typing import Annotated, ClassVar, List, Union
from urllib.parse import urlunparse
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import field_validator
from .__version__ import VERSION
from .account import Account
from .agent import Agent, AgentCustomMethodParams, AgentMethodParams
from .common import (
    ApiResult,
    ApiSuccess,
    decrypt_value,
    encrypt_value,
    log,
    SvBaseModel,
)
from .instructions import display_instructions
from .job import Job, JobContext, Jobs, JobStatus
from .parameter import Parameters
from .server_utils import ErrorResponse, ErrorType, create_error_response
from rich import inspect

insp = inspect


class ServerModel(SvBaseModel):
    """
    API Server for the Supervaize Control.
    """

    model_config = {
        "arbitrary_types_allowed": True  # for FastAPI
    }
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    scheme: str
    host: str
    port: int
    environment: str
    mac_addr: str
    debug: bool
    agents: list[Agent]
    app: FastAPI
    reload: bool
    account: Account
    private_key: rsa.RSAPrivateKey = None
    public_key: rsa.RSAPublicKey = None

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


default_router = APIRouter()


@default_router.get("/jobs/{job_id}", tags=["Jobs"], response_model=Job)
def get_job_status(job_id: str):
    """Get the status of a job by its ID

    Args:
        job_id (str): The ID of the job to get status for

    Returns:
        Job: The job object if found

    Raises:
        HTTPException: If job not found
    """
    job = Jobs().get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
        )
    return job


@default_router.get("/jobs", tags=["Jobs"], response_model=dict[str, List[Job]])
def get_all_jobs(
    skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Number of jobs to return"
    ),
    status: JobStatus | None = Query(default=None, description="Filter jobs by status"),
):
    """Get all jobs across all agents with pagination and optional status filtering"""
    try:
        jobs_registry = Jobs()
        all_jobs = {}

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
        error_response = ErrorResponse(
            error="Failed to retrieve jobs",
            error_type=ErrorType.INTERNAL_ERROR,
            detail=str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(error_response),
        )


async def get_server() -> "Server":
    """Dependency to get the current server instance"""
    # This will be replaced with the actual server instance at runtime
    # through the Server class's create_agent_routes method
    return None


@default_router.get("/agents", tags=["Agents"], response_model=List[Agent])
async def get_all_agents(
    skip: int = Query(default=0, ge=0, description="Number of agents to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Number of agents to return"
    ),
    server: Annotated["Server", Depends(get_server)] = None,
) -> List[Agent]:
    """Get all registered agents with pagination"""
    try:
        res = [a.registration_info for a in server.agents[skip : skip + limit]]
        return res
    except Exception as e:
        return create_error_response(
            ErrorType.INTERNAL_ERROR,
            f"Failed to retrieve agents: {str(e)}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@default_router.get("/agent/{agent_id}", tags=["Agents"], response_model=Agent)
async def get_agent_details(
    agent_id: str,
    server: Annotated["Server", Depends(get_server)] = None,
) -> dict | JSONResponse:
    """Get details of a specific agent by ID"""
    try:
        for agent in server.agents:
            if agent.id == agent_id:
                return agent.registration_info

        return create_error_response(
            ErrorType.AGENT_NOT_FOUND,
            f"Agent with ID '{agent_id}' not found",
            status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return create_error_response(
            ErrorType.INTERNAL_ERROR,
            f"Failed to retrieve agent details: {str(e)}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class Server(ServerModel):
    def __init__(
        self,
        account: Account,
        agents: list[Agent],
        scheme: str = "http",
        environment: str = os.getenv("SUPERVAIZE_CONTROL_ENVIRONMENT", "dev"),
        host: str = os.getenv("SUPERVAIZE_CONTROL_HOST", "0.0.0.0"),
        port: int = int(os.getenv("SUPERVAIZE_CONTROL_PORT", 8001)),
        debug: bool = False,
        reload: bool = False,
        **kwargs,
    ):
        """Initialize the API server.

        Args:
            account (Account): The account to use for the server.
            agents (list[Agent]): The list of agents to use for the server.
            scheme (str, optional): The scheme to use for the server (e.g. 'http', 'https'). Defaults to "http".
            environment (str, optional): The environment to use for the server (e.g. 'dev', 'staging', 'production'). Defaults to os.getenv("SUPERVAIZE_CONTROL_ENVIRONMENT", "dev").
            host (str, optional): The host to use for the server (without '://'). Defaults to 0.0.0.0 if no value in Env "SUPERVAIZE_CONTROL_HOST".
            port (int, optional): The port to use for the server. Defaults 8001 if no value in Env "SUPERVAIZE_CONTROL_PORT".
            debug (bool, optional): Whether to run in debug mode. Defaults to False.
            reload (bool, optional): Whether to reload the server on code changes. Defaults to False.
        """
        # Set appropriate log level based on debug mode
        # log_level = "DEBUG" if debug else "ERROR"

        # log.configure(handlers=[{"sink": "sys.stderr", "level": log_level}])

        kwargs["account"] = account
        kwargs["scheme"] = scheme
        kwargs["host"] = host
        kwargs["port"] = port
        kwargs["environment"] = environment
        kwargs["debug"] = debug
        kwargs["app"] = FastAPI(
            debug=debug,
            title="Supervaize Control API",
            description=(
                "API for controlling and managing Supervaize agents. More information at "
                "[https://supervaize.com/docs/integration](https://supervaize.com/docs/integration)"
            ),
            version=VERSION,
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
        )
        kwargs["reload"] = reload
        kwargs["mac_addr"] = "-".join(
            ("%012X" % uuid.getnode())[i : i + 2] for i in range(0, 12, 2)
        )

        kwargs["private_key"] = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        kwargs["public_key"] = kwargs["private_key"].public_key()
        kwargs["agents"] = agents
        super().__init__(**kwargs)
        self.add_route(default_router)
        self.create_utils_routes()
        self.create_agent_routes()

        # Override the get_server dependency to return this instance
        async def get_current_server() -> "Server":
            return self

        # Update the dependency
        self.app.dependency_overrides[get_server] = get_current_server

    @property
    def url(self):
        return urlunparse((self.scheme, f"{self.host}:{self.port}", "", "", "", ""))

    @property
    def uri(self):
        return f"server:{self.mac_addr}"

    @property
    def registration_info(self):
        return {
            "url": self.url,
            "uri": self.uri,
            "environment": self.environment,
            "public_key": self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8"),
            "agents": [agent.registration_info for agent in self.agents],
        }

    def add_route(self, route: str):
        self.app.include_router(route)

    def create_utils_routes(self):
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

    def create_agent_routes(self):
        for agent in self.agents:
            tags = [f"Agent {agent.name} v{agent.version}"]

            router = APIRouter(prefix=f"/agents/{agent.slug}", tags=tags)

            async def get_agent() -> Agent:
                return agent

            @router.get(
                "/",
                summary="Get agent information",
                description="Detailed information about the agent, returned as a JSON object with Agent class fields",
                response_model=Agent,
                responses={status.HTTP_200_OK: {"model": Agent}},
                tags=tags,
            )
            async def agent_info(agent: Agent = Depends(get_agent)) -> Agent:
                log.info(f"Getting agent info for {agent.name}")
                return agent.registration_info

            @router.post(
                "/jobs",
                summary=f"Start a job with agent : {agent.name}",
                description=f"{agent.job_start_method.description}",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": agent.job_start_method},
                    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
                    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
                },
                tags=tags,
                response_model=Job,
                status_code=status.HTTP_202_ACCEPTED,
            )
            async def start_job(
                background_tasks: BackgroundTasks,
                body_params: agent.job_start_method.job_model = Body(...),
                agent: Agent = Depends(get_agent),
            ) -> Job | JSONResponse:
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
                            status.HTTP_409_CONFLICT,
                        )
                    return create_error_response(
                        ErrorType.INVALID_REQUEST, str(e), status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    return create_error_response(
                        ErrorType.INTERNAL_ERROR,
                        str(e),
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            @router.get(
                "/jobs",
                summary=f"Get all jobs for agent: {agent.name}",
                description="Get all jobs for this agent with pagination and optional status filtering",
                response_model=List[Job],
                responses={
                    status.HTTP_200_OK: {"model": List[Job]},
                    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
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
                        ErrorType.INVALID_REQUEST, str(e), status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    return create_error_response(
                        ErrorType.INTERNAL_ERROR,
                        str(e),
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            @router.get(
                "/jobs/{job_id}",
                summary=f"Get job status for agent: {agent.name}",
                description="Get the status and details of a specific job",
                response_model=Job,
                responses={
                    status.HTTP_200_OK: {"model": Job},
                    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
                    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
                },
                tags=tags,
            )
            async def get_job_status(
                job_id: str, agent: Agent = Depends(get_agent)
            ) -> Job | JSONResponse:
                """Get the status of a job by its ID for this specific agent"""
                try:
                    job = Jobs().get_job(job_id, agent_name=agent.name)
                    if not job:
                        return create_error_response(
                            ErrorType.JOB_NOT_FOUND,
                            f"Job with ID {job_id} not found for agent {agent.name}",
                            status.HTTP_404_NOT_FOUND,
                        )
                    return job
                except ValueError as e:
                    return create_error_response(
                        ErrorType.INVALID_REQUEST, str(e), status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    return create_error_response(
                        ErrorType.INTERNAL_ERROR,
                        str(e),
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            @router.post(
                "/stop",
                summary="Stop the agent",
                description="Stop the agent",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": Agent},
                },
                tags=tags,
            )
            async def stop_agent(
                params: AgentMethodParams, agent: Agent = Depends(get_agent)
            ) -> Agent:
                log.info(f"Stopping agent {agent.name} with params {params}")
                return agent.stop(params)

            @router.post(
                "/status",
                summary="Status the agent",
                description="Get the status of the agent",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": Agent},
                },
                tags=tags,
            )
            async def status_agent(
                params: AgentMethodParams, agent: Agent = Depends(get_agent)
            ) -> Agent:
                log.info(f"Getting status of agent {agent.name} with params {params}")
                return agent.status(params)

            @router.post(
                "/custom",
                summary="Trigger a custom method",
                description="Trigger a custom method",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": Agent},
                    status.HTTP_405_METHOD_NOT_ALLOWED: {"model": Agent},
                },
                tags=tags,
            )
            async def custom_method(
                params: AgentCustomMethodParams, agent: Agent = Depends(get_agent)
            ):
                log.info(
                    f"Triggering custom method {params.method_name} for agent {agent.name} with params {params.params}"
                )
                return agent.custom_method(params)

            self.app.include_router(router)

    def launch(self, log_level: str | None = "INFO"):
        """_summary_

        Args:
            log_level (str | None, optional): _description_. Defaults to "INFO". If explicitly set to None, the handler is not added.
        """
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

    def instructions(self):
        server_url = f"http://{self.host}:{self.port}"
        display_instructions(
            server_url, f"Starting server on {server_url} \n Waiting for instructions.."
        )

    def decrypt(self, encrypted_parameters: str) -> Union[str, None]:
        print("decrypt")
        print(encrypted_parameters)
        res = decrypt_value(encrypted_parameters, self.private_key)
        print(res)
        return decrypt_value(encrypted_parameters, self.private_key)

    def encrypt(self, parameters: str) -> Union[str, None]:
        return encrypt_value(parameters, self.public_key)
