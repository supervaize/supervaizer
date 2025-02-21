import os
from typing import ClassVar
from fastapi import APIRouter, Depends, FastAPI, status, Body
from loguru import logger
from pydantic import BaseModel, field_validator
from urllib.parse import urlunparse
from .__version__ import VERSION
from .agent import Agent, AgentCustomMethodParams, AgentMethodParams
from .instructions import display_instructions

log = logger


class ServerModel(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True  # for FastAPI
    }
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    scheme: str
    host: str
    port: int
    environment: str
    debug: bool
    agents: list[Agent]
    app: FastAPI
    reload: bool

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


default_router = APIRouter()


@default_router.get("/", tags=["Public"])
def read_root(agents: list[Agent]):
    return {
        "message": f"Welcome to the Supervaize Control API v{VERSION}. Use the /trigger endpoint to run the analysis."
    }


class Server(ServerModel):
    def __init__(
        self,
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
            scheme (str, optional): The scheme to use for the server (e.g. 'http', 'https'). Defaults to "http".
            environment (str, optional): The environment to use for the server (e.g. 'dev', 'staging', 'production'). Defaults to os.getenv("SUPERVAIZE_CONTROL_ENVIRONMENT", "dev").
            host (str, optional): The host to use for the server (without '://'). Defaults to 0.0.0.0 if no value in Env "SUPERVAIZE_CONTROL_HOST".
            port (int, optional): The port to use for the server. Defaults 8001 if no value in Env "SUPERVAIZE_CONTROL_PORT".
            debug (bool, optional): Whether to run in debug mode. Defaults to False.
            reload (bool, optional): Whether to reload the server on code changes. Defaults to False.
        """
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
                "name": "License TBD - No responsibility for any issues",
                "url": "https://TBD.com",
            },
        )
        kwargs["reload"] = reload
        super().__init__(**kwargs)
        self.add_route(default_router)
        self.create_agent_routes()

    @property
    def url(self):
        return urlunparse((self.scheme, f"{self.host}:{self.port}", "", "", "", ""))

    def add_route(self, route: str):
        self.app.include_router(route)

    def create_agent_routes(self):
        for agent in self.agents:
            tags = [f"Agent {agent.name} v{agent.version}"]

            router = APIRouter(prefix=f"/agent/{agent.slug}", tags=tags)

            async def get_agent() -> Agent:
                return agent

            @router.get(
                "/info",
                summary="Get agent information",
                description="Detailed information about the agent, returned as a JSON object with Agent class fields",
                response_model=Agent,
                responses={status.HTTP_200_OK: {"model": Agent}},
                tags=tags,
            )
            async def agent_info(agent: Agent = Depends(get_agent)) -> Agent:
                log.info(f"Getting agent info for {agent.name}")
                return agent

            @router.post(
                "/start",
                summary="Start the agent",
                description="Start the agent with optional parameters",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": Agent},
                },
                tags=tags,
                response_model=Agent,
                status_code=status.HTTP_202_ACCEPTED,
            )
            async def start_agent(
                params: AgentMethodParams = Body(...), agent: Agent = Depends(get_agent)
            ) -> Agent:
                log.info(f"Starting agent {agent.name} with params {params} ")
                return agent.start(params)

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

    def launch(self):
        import uvicorn

        self.instructions()
        uvicorn.run(self.app, host=self.host, port=self.port, reload=self.reload)

    def instructions(self):
        server_url = f"http://{self.host}:{self.port}"
        display_instructions(
            server_url, f"Starting server on {server_url} \n Waiting for instructions.."
        )
