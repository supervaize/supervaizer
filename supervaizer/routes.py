# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import traceback
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)
from cryptography.hazmat.primitives import serialization
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Security,
    status as http_status,
)
from fastapi.responses import JSONResponse
from rich import inspect
from supervaizer.agent import (
    Agent,
    AgentCustomMethodParams,
    AgentMethodParams,
    AgentResponse,
)
from supervaizer.common import log
from supervaizer.job import Job, JobContext, Jobs, JobResponse
from supervaizer.job_service import service_job_start
from supervaizer.lifecycle import EntityStatus
from supervaizer.server_utils import ErrorResponse, ErrorType, create_error_response

if TYPE_CHECKING:
    from enum import Enum

    from supervaizer.server import Server

T = TypeVar("T")

insp = inspect


def handle_route_errors(
    job_conflict_check: bool = False,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Awaitable[Union[T, JSONResponse]]]
]:
    """
    Decorator to handle common route error patterns.

    Args:
        job_conflict_check: If True, checks for "already exists" in ValueError messages
                          and returns a conflict error response
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[Union[T, JSONResponse]]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Union[T, JSONResponse]:
            try:
                result: T = await func(*args, **kwargs)
                return result

            except HTTPException as e:
                return create_error_response(
                    error_type=ErrorType.INVALID_REQUEST,
                    detail=e.detail if hasattr(e, "detail") else str(e),
                    status_code=e.status_code,
                )
            except ValueError as e:
                if job_conflict_check and "already exists" in str(e):
                    return create_error_response(
                        ErrorType.JOB_ALREADY_EXISTS,
                        str(e),
                        http_status.HTTP_409_CONFLICT,
                    )
                return create_error_response(
                    error_type=ErrorType.INVALID_REQUEST,
                    detail=str(e),
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    traceback=f"Error at line {traceback.extract_tb(e.__traceback__)[-1].lineno}:\n"
                    f"{traceback.format_exc()}",
                )
            except Exception as e:
                return create_error_response(
                    error_type=ErrorType.INTERNAL_ERROR,
                    detail=str(e),
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    traceback=f"Error at line {traceback.extract_tb(e.__traceback__)[-1].lineno}:\n"
                    f"{traceback.format_exc()}",
                )

        return wrapper

    return decorator


async def get_server() -> "Server":
    """Get the current server instance."""
    raise NotImplementedError("This function should be overridden by the server")


def create_default_routes(server: "Server") -> APIRouter:
    """Create default routes for the server."""
    router = APIRouter(prefix="/supervaizer", tags=["Supervision"])

    @router.get(
        "/jobs/{job_id}",
        response_model=Job,
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_job_status(job_id: str) -> Job:
        """Get the status of a job by its ID"""
        job = Jobs().get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found",
            )
        return job

    @router.get(
        "/jobs",
        response_model=Dict[str, List[JobResponse]],
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_all_jobs(
        skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
        limit: int = Query(
            default=100, ge=1, le=1000, description="Number of jobs to return"
        ),
        status: Optional[EntityStatus] = Query(
            default=None, description="Filter jobs by status"
        ),
    ) -> Dict[str, List[JobResponse]]:
        """Get all jobs across all agents with pagination and optional status filtering"""
        jobs_registry = Jobs()
        all_jobs: Dict[str, List[JobResponse]] = {}

        for agent_name, agent_jobs in jobs_registry.jobs_by_agent.items():
            filtered_jobs = list(agent_jobs.values())

            # Apply status filter if specified
            if status:
                filtered_jobs = [job for job in filtered_jobs if job.status == status]

            # Apply pagination
            filtered_jobs = filtered_jobs[skip : skip + limit]

            if filtered_jobs:  # Only include agents that have jobs after filtering
                # Convert each Job object to JobResponse
                jobs_responses = [
                    JobResponse(
                        job_id=job.id,
                        status=job.status,
                        message=f"Job {job.id} status: {job.status.value}",
                        payload=job.payload,
                    )
                    for job in filtered_jobs
                ]

                all_jobs[agent_name] = jobs_responses

        return all_jobs

    @router.get("/agents", response_model=List[AgentResponse])
    @handle_route_errors()
    async def get_all_agents(
        skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
        limit: int = Query(
            default=100, ge=1, le=1000, description="Number of jobs to return"
        ),
    ) -> List[AgentResponse]:
        """Get all registered agents with pagination"""
        if not server:
            raise ValueError("Server instance not found")
        return [
            AgentResponse(**a.registration_info)
            for a in server.agents[skip : skip + limit]
        ]

    @router.get("/agent/{agent_id}", response_model=AgentResponse)
    @handle_route_errors()
    async def get_agent_details(
        agent_id: str,
    ) -> AgentResponse:
        """Get details of a specific agent by ID"""
        if not server:
            raise ValueError("Server instance not found")
        for agent in server.agents:
            if agent.id == agent_id:
                return AgentResponse(**agent.registration_info)

        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID '{agent_id}' not found",
        )

    return router


def create_utils_routes(server: "Server") -> APIRouter:
    """Create utility routes."""
    router = APIRouter(prefix="/supervaizer/utils", tags=["Supervision"])

    @router.get(
        "/public_key",
        summary="Get server's public key",
        description="Returns the server's public key in PEM format",
        response_model=str,
    )
    @handle_route_errors()
    async def get_public_key() -> str:
        pem = server.public_key.public_bytes(
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
    @handle_route_errors()
    async def encrypt_string(text: str = Body(...)) -> str:
        return server.encrypt(text)

    return router


def create_agents_routes(server: "Server") -> APIRouter:
    """Create agent-specific routes."""
    routers = APIRouter(prefix="/supervaizer", tags=["Supervision"])
    for agent in server.agents:
        routers.include_router(create_agent_route(server, agent))
    return routers


def create_agent_route(server: "Server", agent: Agent) -> APIRouter:
    """Create agent-specific routes."""
    # tags: list[str | Enum] = [f"Agent {agent.name} v{agent.version}"]
    tags: list[str | Enum] = ["Supervision"]
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
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def agent_info(agent: Agent = Depends(get_agent)) -> AgentResponse:
        log.info(f"📥  GET /[Agent info] {agent.name}")
        return AgentResponse(
            **agent.registration_info,
        )

    agent_job_model_name = f"{agent.slug}_Start_Job_Model"
    # Create the dynamic model with the custom name for FastAPI documentation
    AgentStartJobModel = type(
        agent_job_model_name,
        (agent.methods.job_start.job_model,),  # type: ignore
        {},
    )

    @router.post(
        "/jobs",
        summary=f"Start a job with agent: {agent.name}",
        description=f"{agent.methods.job_start.description}",
        responses={
            http_status.HTTP_202_ACCEPTED: {"model": Job},
            http_status.HTTP_409_CONFLICT: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        response_model=Job,
        status_code=http_status.HTTP_202_ACCEPTED,
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors(job_conflict_check=True)
    async def start_job(
        background_tasks: BackgroundTasks,
        body_params: AgentStartJobModel = Body(...),  # type: ignore
        agent: Agent = Depends(get_agent),
    ) -> Union[Job, JSONResponse]:
        """Start a new job for this agent"""
        log.info(f"📥 POST /jobs [Start job] {agent.name} with params {body_params}")
        sv_context: JobContext = body_params.job_context  # type: ignore[attr-defined]
        job_fields = body_params.job_fields.to_dict()  # type: ignore[attr-defined]

        # Get job encrypted parameters if available
        encrypted_agent_parameters = getattr(
            body_params, "encrypted_agent_parameters", None
        )

        # Delegate job creation and scheduling to the service
        new_job = await service_job_start(
            server,
            background_tasks,
            agent,
            sv_context,
            job_fields,
            encrypted_agent_parameters,
        )

        return new_job

    @router.get(
        "/jobs",
        summary=f"Get all jobs for agent: {agent.name}",
        description="Get all jobs for this agent with pagination and optional status filtering",
        response_model=List[JobResponse],
        responses={
            http_status.HTTP_200_OK: {"model": List[JobResponse]},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_agent_jobs(
        agent: Agent = Depends(get_agent),
        skip: int = Query(default=0, ge=0, description="Number of jobs to skip"),
        limit: int = Query(
            default=100, ge=1, le=1000, description="Number of jobs to return"
        ),
        status: EntityStatus | None = Query(
            default=None, description="Filter jobs by status"
        ),
    ) -> List[JobResponse] | JSONResponse:
        """Get all jobs for this agent"""
        log.info(f"📥  GET /jobs [Get agent jobs] {agent.name}")
        jobs = list(Jobs().get_agent_jobs(agent.name).values())

        # Apply status filter if specified
        if status:
            jobs = [job for job in jobs if job.status == status]

        # Apply pagination
        jobs = jobs[skip : skip + limit]

        # Convert Job objects to JobResponse objects
        return [
            JobResponse(
                job_id=job.id,
                status=job.status,
                message=f"Job {job.id} status: {job.status.value}",
                payload=job.payload,
            )
            for job in jobs
        ]

    @router.get(
        "/jobs/{job_id}",
        summary=f"Get job status for agent: {agent.name}",
        description="Get the status and details of a specific job",
        response_model=Job,
        responses={
            http_status.HTTP_200_OK: {"model": Job},
            http_status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_job_status(job_id: str, agent: Agent = Depends(get_agent)) -> Job:
        """Get the status of a job by its ID for this specific agent"""
        log.info(f"📥  GET /jobs/{job_id} [Get job status] {agent.name}")
        job = Jobs().get_job(job_id, agent_name=agent.name)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found for agent {agent.name}",
            )
        return job

    @router.post(
        "/stop",
        summary=f"Stop the agent: {agent.name}",
        description="Stop the agent",
        responses={
            http_status.HTTP_202_ACCEPTED: {"model": AgentResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def stop_agent(
        params: AgentMethodParams, agent: Agent = Depends(get_agent)
    ) -> AgentResponse:
        log.info(f"📥  POST /stop [Stop agent] {agent.name} with params {params}")
        result = agent.job_stop(params.params)
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
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def status_agent(
        params: AgentMethodParams, agent: Agent = Depends(get_agent)
    ) -> AgentResponse:
        log.info(f"📥  POST /status [Status agent] {agent.name} with params {params}")
        result = agent.job_status(params.params)
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
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def custom_method(
        params: AgentCustomMethodParams, agent: Agent = Depends(get_agent)
    ) -> AgentResponse:
        log.info(
            f"POST /custom [Custom method] {params.method_name} for agent {agent.name} with params {params.params}"
        )
        if not (agent.methods.custom and params.method_name in agent.methods.custom):
            raise HTTPException(
                status_code=http_status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="Custom method not found",
            )

        method = agent.methods.custom[params.method_name]
        result = method(params.params) if callable(method) else method
        log.debug(f"[Custom method] {params.method_name} result: {result}")

        return AgentResponse(
            name=agent.name,
            id=agent.id,
            version=agent.version,
            api_path=agent.path,
            description=agent.description,
            methods=agent.methods,
        )

    @router.post(
        "/parameters",
        summary=f"Server updates agent: {agent.name}",
        description="Server updates agent onboarding status and/or encrypted parameters",
        response_model=AgentResponse,
        responses={
            http_status.HTTP_200_OK: {"model": AgentResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def server_update_agent(
        onboarding_status: Optional[str] = Body(None),
        parameters_encrypted: Optional[str] = Body(None),
        agent: Agent = Depends(get_agent),
    ) -> AgentResponse:
        log.info(f"📥 POST /server_update [Server updates agent] {agent.name}")

        if onboarding_status is not None:
            agent.server_agent_onboarding_status = onboarding_status
        if parameters_encrypted is not None:
            agent.update_parameters_from_server(server, parameters_encrypted)
        # import importlib

        # importlib.reload(Agent)
        return AgentResponse(**agent.registration_info)

    return router
