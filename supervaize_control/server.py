from .__version__ import VERSION
from fastapi import FastAPI, APIRouter, Depends
from .agent import Agent
import os

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
            description="API for controlling and managing Supervaize agents. Documentation ~/redoc",
            version=VERSION,
            terms_of_service="https://supervaize.com/terms/",
            contact={
                "name": "Support Team",
                "url": "https://example.com/contact/",
                "email": "support@example.com",
            },
            license_info={
                "name": "MIT License",
                "url": "https://opensource.org/licenses/MIT",
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
            router = APIRouter(
                prefix=f"/agent/{agent.slug}", tags=[f"Agent: {agent.name}"]
            )

            async def get_agent() -> Agent:
                return agent

            @router.get("/ ")
            async def agent_info(agent: Agent = Depends(get_agent)):
                return {
                    "name": agent.name,
                    "status": "active",
                    "type": agent.__class__.__name__,
                }

            @router.post("/trigger")
            async def trigger_agent(agent: Agent = Depends(get_agent)):
                return {"message": f"Triggered agent {agent.name}"}

            self.app.include_router(router)

    def launch(self):
        import uvicorn

        uvicorn.run(self.app, host=self.host, port=self.port, reload=self.reload)
