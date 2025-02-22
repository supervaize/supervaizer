# main.py

import os
import subprocess
import sys

from fastapi import FastAPI, HTTPException
from loguru import logger as log
from pydantic import BaseModel

from .__version__ import VERSION
from .agent import AgentService

app = FastAPI(
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
PORT = int(os.getenv("SUPERVAIZE_CONTROL_PORT", 8001))
IP = os.getenv("SUPERVAIZE_CONTROL_IP", "0.0.0.0")


class AnalysisRequest(BaseModel):
    business_description: str


@app.get(
    "/agents/{agent_id}",
    response_model=AgentService,
    summary="Get Agent",
    description="Retrieve an agent by its unique ID.",
    tags=["Agents"],
)
def get_agent(agent_id: int):
    # Dummy data for illustration
    return AgentService(id=agent_id, name="Agent Smith", status="active")


@app.get("/", tags=["Public"])
def read_root():
    return {
        "message": f"Welcome to the Supervaize Control API v{VERSION}. Use the /commands endpoint to run the commands."
    }


@app.get("/agent/status", tags=["Authenticated"])
def agent_status():
    result = AgentService.status()
    return {"status": result}


@app.get("/commands", tags=["Authenticated"])
def trigger_analysis(business_description: str):
    """


    - **business_description**: Description of your business to find competitors.
    """
    if not business_description:
        raise HTTPException(
            status_code=400, detail="business_description query parameter is required."
        )

    try:
        # Execute the competitor_script.py using subprocess
        # Ensure the Python interpreter and script path are correct
        result = subprocess.run(
            [sys.executable, "competitor_script.py", business_description],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse the output (assuming JSON)
        import json

        response = json.loads(result.stdout)
        return response
    except subprocess.CalledProcessError as e:
        # Capture script's stderr
        error_message = (
            e.stderr
            if e.stderr
            else "An error occurred while running the competitor analysis script."
        )
        raise HTTPException(status_code=500, detail=error_message)
    except json.JSONDecodeError:
        # Handle cases where script output is not JSON
        raise HTTPException(
            status_code=500, detail="Invalid response from competitor analysis script."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/commands", tags=["Authenticated"])
def trigger_analysis_post(request: AnalysisRequest):
    """
    Trigger the competitor analysis script with a JSON payload.

    - **business_description**: Description of your business to find competitors.
    """
    if not request.business_description:
        raise HTTPException(
            status_code=400,
            detail="business_description is required in the request body.",
        )

    try:
        # Execute the competitor_script.py using subprocess
        # Pass the business_description as an argument
        log.info(f"Triggering analysis for {request.business_description}")
        result = subprocess.run(
            [sys.executable, "competitor_script.py", request.business_description],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse the output (assuming JSON)
        import json

        response = json.loads(result.stdout)
        return response
    except subprocess.CalledProcessError as e:
        # Capture script's stderr
        error_message = (
            e.stderr
            if e.stderr
            else "An error occurred while running the competitor analysis script."
        )
        raise HTTPException(status_code=500, detail=error_message)
    except json.JSONDecodeError:
        # Handle cases where script output is not JSON
        raise HTTPException(
            status_code=500, detail="Invalid response from competitor analysis script."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def controller_start():
    import uvicorn

    uvicorn.run("controller:app", host=IP, port=PORT, reload=True)
