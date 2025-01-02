from .__version__ import VERSION
from fastapi import FastAPI, APIRouter, Depends, status
from .agent import Agent, AgentMethodParams, AgentCustomMethodParams
import os
from .instructions import display_instructions
from loguru import logger

log = logger

default_router = APIRouter()


@default_router.get("/", tags=["Public"])
def read_root(agents: list[Agent]):
    return {
        "message": f"Welcome to the Supervaize Control API v{VERSION}. Use the /trigger endpoint to run the analysis."
    }


class Server:
    PORT = int(os.getenv("SUPERVIZE_CONTROL_PORT", 8001))
    HOST = os.getenv("SUPERVIZE_CONTROL_HOST", "0.0.0.0")

    def __init__(
        self,
        agents: list[Agent],
        host: str = HOST,
        port: int = PORT,
        debug: bool = False,
    ):
        self.agents: list[Agent] = agents
        self.host: str = host
        self.port: int = port
        self.reload: bool = debug
        self.app = FastAPI(
            title="Supervaize Control API",
            description="API for controlling and managing Supervaize agents. More information at [https://supervaize.com/docs/integration](https://supervaize.com/docs/integration)",
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
        self.add_route(default_router)
        self.create_agent_routes()
        self.debug = debug

    @property
    def uri(self):
        return f"server:{self.host}:{self.port}:app:{self.app}"

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
                description="Start the agent",
                responses={
                    status.HTTP_202_ACCEPTED: {"model": Agent},
                },
                tags=tags,
            )
            async def start_agent(
                params: AgentMethodParams | None, agent: Agent = Depends(get_agent)
            ) -> Agent:
                log.info(f"Starting agent {agent.name} with params {params}")
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
                params: AgentMethodParams | None, agent: Agent = Depends(get_agent)
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
