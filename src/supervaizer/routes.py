# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import traceback
from functools import wraps
from pathlib import Path
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
    Request,
    Security,
    status as http_status,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from supervaizer.agent import (
    Agent,
    AgentMethodParams,
    AgentResponse,
)
from supervaizer.case import CaseNodeUpdate, Cases
from supervaizer.common import SvBaseModel, log
from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.job_service import service_job_custom, service_job_start
from supervaizer.lifecycle import EntityStatus
from supervaizer.server_utils import ErrorResponse, ErrorType, create_error_response

if TYPE_CHECKING:
    from enum import Enum

    from supervaizer.server import Server

T = TypeVar("T")


class CaseUpdateRequest(SvBaseModel):
    """Request model for updating a case with answer to a question."""

    answer: Dict[str, Any]
    message: Optional[str] = None


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
            # log.debug(f"------[DEBUG]----------\n args :{args} \n kwargs :{kwargs}")
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
        response_model=JobResponse,
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_job_status(job_id: str) -> JobResponse:
        """Get the status of a job by its ID"""
        job = Jobs().get_job(job_id, include_persisted=True)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found §SRCG01",
            )
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message=f"Job {job.id} status: {job.status.value}",
            payload=job.payload,
        )

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
                jobs_responses = []
                for job in filtered_jobs:
                    job_status = job.status
                    if isinstance(job_status, str):
                        try:
                            job_status = EntityStatus(job_status)
                        except ValueError:
                            job_status = EntityStatus.IN_PROGRESS  # fallback or default
                    jobs_responses.append(
                        JobResponse(
                            job_id=job.id,
                            status=job_status,
                            message=f"Job {job.id} status: {job_status.value}",
                            payload=job.payload,
                        )
                    )

                all_jobs[agent_name] = jobs_responses

        return all_jobs

    @router.post(
        "/jobs/{job_id}/cases/{case_id}/update",
        summary="Update case with answer to question",
        description="Provide an answer to a question that was requested by a case step",
        response_model=Dict[str, str],
        responses={
            http_status.HTTP_200_OK: {"model": Dict[str, str]},
            http_status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
            http_status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def update_case_with_answer(
        job_id: str,
        case_id: str,
        request: CaseUpdateRequest = Body(...),
    ) -> Dict[str, str]:
        """Update a case with an answer to a question requested by a case step"""
        log.info(
            f"📥 POST /jobs/{job_id}/cases/{case_id}/update [Update case with answer]"
        )

        # Get the job first
        job = Jobs().get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found §SRCU01",
            )

        # Get the case from the Cases registry
        case = Cases().get_case(case_id, job_id)
        if not case:
            log.warning(f"Case with ID {case_id} not found for job {job_id} §SRCU02")
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Case with ID {case_id} not found for job {job_id} §SRCU02",
            )
        # Check if the case is in AWAITING status (waiting for human input)
        if case.status != EntityStatus.AWAITING:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Case {case_id} is not awaiting input. Current status: {case.status.value} §SRC01",
            )

        # Create a case node update with the answer
        update = CaseNodeUpdate(
            name="Human Input Response",
            payload={
                "answer": request.answer,
                "message": request.message,
                "response_type": "human_input",
            },
            is_final=False,
        )

        # Update the case with the answer
        # case.update(update) - Redundant, receive_human_input calls update()

        # Transition the case from AWAITING to IN_PROGRESS
        case.receive_human_input(update)

        # TODO CALL CUSTOM HOOKS HERE - AS DEFINED IN THE AGENT CONFIGURATION
        # TODO REDEFINE AGENT TO ADD CUSTOM HOOKS HERE

        log.info(
            f"[Case update] Job {job_id}, Case {case_id} - Answer processed successfully"
        )

        return {
            "status": "success",
            "message": f"Answer received and processed for case {case_id} in job {job_id}",
            "job_id": job_id,
            "case_id": case_id,
            "case_status": case.status.value,
        }

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
        # Add custom method routes for each agent
        if agent.methods and agent.methods.custom:
            routers.include_router(create_agent_custom_routes(server, agent))
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

    @router.get(
        f"/{agent.instructions_path}",
        summary=f"Get supervaize instructions page for agent {agent.name}",
        description="HTML page displaying agent registration information and instructions",
        response_class=HTMLResponse,
        tags=tags,
    )
    @handle_route_errors()
    async def supervaize_instructions(
        request: Request, agent: Agent = Depends(get_agent)
    ) -> Response:
        """Serve the supervaize instructions HTML page for this agent."""
        log.info(
            f"📥  GET /{agent.instructions_path} [Supervaize Instructions] for agent{agent.name}"
        )

        registration_info = agent.registration_info

        # Convert instructions_path string to Path object
        instructions_path = Path(agent.instructions_path)

        # Check if file exists - if not, return empty HTML
        if not instructions_path.exists() or not instructions_path.is_file():
            return HTMLResponse(content="", status_code=200)

        # Serve the file (check if it's a Jinja2 template or static HTML)
        with open(instructions_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Simple check: if it contains Jinja2 syntax, render as template
            if "{{" in content or "{%" in content:
                # Render as Jinja2 template
                custom_templates = Jinja2Templates(
                    directory=str(instructions_path.parent)
                )
                return custom_templates.TemplateResponse(
                    instructions_path.name,
                    {
                        "request": request,
                        "registration_info": registration_info,
                    },
                )
            else:
                # Serve as static HTML file
                return FileResponse(
                    str(instructions_path),
                    media_type="text/html",
                )

    @router.post(
        "/validate-agent-parameters",
        summary=f"Validate agent parameters for agent: {agent.name}",
        description="Validate agent configuration parameters (secrets, API keys, etc.) before starting a job",
        response_model=Dict[str, Any],
        responses={
            http_status.HTTP_200_OK: {"model": Dict[str, Any]},
            http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def validate_agent_parameters(
        body_params: Any = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> Dict[str, Any]:
        """Validate agent parameters for this agent"""
        log.info(
            f"📥 POST /validate-agent-parameters [Validate agent parameters] {agent.name}"
        )

        if not agent.parameters_setup:
            result = {
                "valid": True,
                "message": "Agent has no parameter setup defined",
                "errors": [],
                "invalid_parameters": {},
            }
            log.info(f"📤 Agent {agent.name}: No parameter setup defined → {result}")
            return result

        if body_params is None:
            body_params = {}

        encrypted_agent_parameters = body_params.get("encrypted_agent_parameters")

        agent_parameters: Dict[str, Any] = {}
        if encrypted_agent_parameters:
            # Basic debug trace
            log.info(
                f"📥 Received encrypted_agent_parameters, length: {len(encrypted_agent_parameters)}"
            )

            try:
                import json

                from supervaizer.common import decrypt_value

                agent_parameters_str = decrypt_value(
                    encrypted_agent_parameters, server.private_key
                )
                agent_parameters = (
                    json.loads(agent_parameters_str) if agent_parameters_str else {}
                )

                # Debug: Log the parsed data type and structure
                log.info(f"🔍 Parsed agent_parameters type: {type(agent_parameters)}")
                if isinstance(agent_parameters, list):
                    log.info(
                        f"🔍 Converting list to dict with {len(agent_parameters)} items"
                    )
                    # Convert list to dict if needed (common when frontend sends array)
                    agent_parameters = {
                        f"param_{i}": param for i, param in enumerate(agent_parameters)
                    }
                elif isinstance(agent_parameters, dict):
                    log.info(
                        f"🔍 Agent parameters keys: {list(agent_parameters.keys())}"
                    )
                else:
                    log.warning(
                        f"🔍 Unexpected type: {type(agent_parameters)}, converting to empty dict"
                    )
                    agent_parameters = {}

            except Exception as e:
                log.error(f"❌ Decryption failed: {type(e).__name__}: {str(e)}")
                result = {
                    "valid": False,
                    "message": f"Failed to decrypt agent parameters: {str(e)}",
                    "errors": [f"Decryption failed: {str(e)}"],
                    "invalid_parameters": {
                        "encrypted_agent_parameters": f"Decryption failed: {str(e)}"
                    },
                }
                log.info(f"📤 Agent {agent.name}: Decryption failed → {result}")
                return result

        # Log the incoming request details
        log.info(
            f"🔍 Agent {agent.name}: Incoming request - encrypted_params: {bool(encrypted_agent_parameters)}, parsed_params: {agent_parameters}"
        )

        # Validate agent parameters
        validation_result = agent.parameters_setup.validate_parameters(agent_parameters)

        result = {
            "valid": validation_result["valid"],
            "message": "Agent parameters validated successfully"
            if validation_result["valid"]
            else "Agent parameter validation failed",
            "errors": validation_result["errors"],
            "invalid_parameters": validation_result["invalid_parameters"],
        }

        log.info(f"📤 Agent {agent.name}: Validation result → {result}")
        return result

    @router.post(
        "/validate-method-fields",
        summary=f"Validate method fields for agent: {agent.name}",
        description="Validate job input fields against the method's field definitions before starting a job",
        response_model=Dict[str, Any],
        responses={
            http_status.HTTP_200_OK: {"model": Dict[str, Any]},
            http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def validate_method_fields(
        body_params: Any = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> Dict[str, Any]:
        """Validate method fields for this agent"""
        log.info(
            f"📥 POST /validate-method-fields [Validate method fields] {agent.name}"
        )

        if body_params is None:
            body_params = {}

        method_name = body_params.get("method_name", "job_start")
        job_fields = body_params.get("job_fields", {})

        # Log the incoming request details
        log.info(
            f"🔍 Agent {agent.name}: Incoming request - method: {method_name}, fields: {job_fields}"
        )

        # Get the method to validate against
        if not agent.methods:
            result = {
                "valid": False,
                "message": "Agent has no methods defined",
                "errors": ["Agent has no methods defined"],
                "invalid_fields": {},
            }
            log.info(f"📤 Agent {agent.name}: No methods defined → {result}")
            return result

        if method_name == "job_start":
            method = agent.methods.job_start
        elif agent.methods.custom and method_name in agent.methods.custom:
            method = agent.methods.custom[method_name]
        else:
            result = {
                "valid": False,
                "message": f"Method '{method_name}' not found",
                "errors": [f"Method '{method_name}' not found"],
                "invalid_fields": {},
            }
            log.info(
                f"📤 Agent {agent.name}: Method '{method_name}' not found → {result}"
            )
            return result

        # Validate method fields
        validation_result = method.validate_method_fields(job_fields)

        result = {
            "valid": validation_result["valid"],
            "message": validation_result["message"],
            "errors": validation_result["errors"],
            "invalid_fields": validation_result["invalid_fields"],
        }

        log.info(
            f"📤 Agent {agent.name}: Method '{method_name}' validation result → {result}"
        )
        return result

    if not agent.methods:
        raise ValueError(f"Agent {agent.name} has no methods defined")

    agent_job_model_name = f"{agent.slug}_Start_Job_Model"
    # Create the dynamic model with the custom name for FastAPI documentation
    _AgentStartAbstractJob = type(
        agent_job_model_name,
        (agent.methods.job_start.job_model,),
        {},
    )

    @router.post(
        "/jobs",
        summary=f"Start a job with agent: {agent.name}",
        description=f"{agent.methods.job_start.description}",
        responses={
            http_status.HTTP_202_ACCEPTED: {"model": Job},
            http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
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
        body_params: Any = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> Union[Job, JSONResponse]:
        """Start a new job for this agent"""
        log.info(f"📥 POST /jobs [Start job] {agent.name} with params {body_params}")

        if body_params is None:
            body_params = {}

        job_context_data = body_params.get("job_context")
        if job_context_data is None:
            raise ValueError("job_context is required")

        sv_context: JobContext = JobContext(**job_context_data)
        job_fields = body_params.get("job_fields", {})

        # Get job encrypted parameters if available
        encrypted_agent_parameters = body_params.get("encrypted_agent_parameters")

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
        response_model=JobResponse,
        responses={
            http_status.HTTP_200_OK: {"model": Job},
            http_status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
            http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
        dependencies=[Security(server.verify_api_key)],
    )
    @handle_route_errors()
    async def get_job_status(
        job_id: str, agent: Agent = Depends(get_agent)
    ) -> JobResponse:
        """Get the status of a job by its ID for this specific agent"""
        log.info(f"📥  GET /jobs/{job_id} [Get job status] {agent.name}")
        job = Jobs().get_job(job_id, agent_name=agent.name, include_persisted=True)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found for agent {agent.name}",
            )
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message=f"Job {job.id} status: {job.status.value}",
            payload=job.payload,
        )

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
        background_tasks: BackgroundTasks,
        params: dict[str, Any] = Body(...),
        agent: Agent = Depends(get_agent),
    ) -> AgentResponse:
        log.info(f"📥  POST /stop [Stop agent] {agent.name} with params {params}")
        # Pass job_context as 'context' parameter to match agent method expectations
        job_context = params.get("job_context", {})
        result = agent.job_stop({"context": job_context})
        res_info = result.registration_info if result else {}
        return AgentResponse(
            name=agent.name,
            id=agent.id,
            version=agent.version,
            api_path=agent.path,
            description=agent.description,
            **res_info,
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


def create_agent_custom_routes(server: "Server", agent: Agent) -> APIRouter:
    """Create individual routes for each custom method of an agent."""
    if not agent.methods or not agent.methods.custom:
        raise ValueError(f"Agent {agent.name} has no custom methods defined")

    tags: list[str | Enum] = ["Supervision"]
    router = APIRouter(
        prefix=agent.path,
        tags=tags,
    )

    async def get_agent() -> Agent:
        return agent

    # Create a route for each custom method
    for method_name, method_config in agent.methods.custom.items():
        # Create the dynamic model with the custom name for FastAPI documentation
        custom_job_model_name = f"{agent.slug}_Custom_{method_name}_Job_Model"
        _AgentCustomAbstractJob = type(
            custom_job_model_name,
            (method_config.job_model,),
            {},
        )

        @router.post(
            f"/custom/{method_name}",
            summary=f"Trigger custom method '{method_name}' for agent: {agent.name}",
            description=f"{method_config.description if hasattr(method_config, 'description') else f'Trigger custom method {method_name}'}",
            response_model=JobResponse,
            responses={
                http_status.HTTP_202_ACCEPTED: {"model": JobResponse},
                http_status.HTTP_400_BAD_REQUEST: {"model": Dict[str, Any]},
                http_status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse},
            },
            dependencies=[Security(server.verify_api_key)],
            name=f"{agent.slug}_custom_{method_name}",  # Unique operation ID
        )
        @handle_route_errors()
        async def custom_method_endpoint(
            background_tasks: BackgroundTasks,
            body_params: Any = Body(...),
            agent: Agent = Depends(get_agent),
        ) -> Union[JobResponse, JSONResponse]:
            log.info(
                f"📥 POST /custom/{method_name} [custom job] {agent.name} with params {body_params}"
            )
            log.info(f"body_params: {body_params}")

            if body_params is None:
                raise ValueError("body_params cannot be None")

            sv_context: JobContext = body_params.job_context
            job_fields = body_params.job_fields.to_dict()

            # Get job encrypted parameters if available
            encrypted_agent_parameters = getattr(
                body_params, "encrypted_agent_parameters", None
            )

            # Delegate job creation and scheduling to the service
            new_job = await service_job_custom(
                method_name,
                server,
                background_tasks,
                agent,
                sv_context,
                job_fields,
                encrypted_agent_parameters,
            )

            # Convert Job to JobResponse to match the endpoint's response model
            return JobResponse(
                job_id=new_job.id,
                status=new_job.status,
                message=f"Custom method '{method_name}' job started for agent {agent.name}",
                payload=new_job.payload,
            )

    return router
