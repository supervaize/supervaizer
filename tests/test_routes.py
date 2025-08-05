from typing import Any
from fastapi.testclient import TestClient
from supervaizer import Server, Agent, Job
from supervaizer.routes import create_utils_routes, create_default_routes


def test_utils_public_key_and_encrypt(server_fixture: Server, mocker: Any) -> None:
    """Test /supervaizer/utils/public_key and /encrypt endpoints."""
    app = server_fixture.app
    app.include_router(create_utils_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test public_key endpoint
    resp = client.get("/supervaizer/utils/public_key", headers=headers)
    assert resp.status_code == 200
    assert "BEGIN PUBLIC KEY" in resp.text

    # Test encrypt endpoint
    test_str = "super_secret"
    resp = client.post("/supervaizer/utils/encrypt", headers=headers, json=test_str)
    assert resp.status_code == 200
    encrypted = resp.text.strip('"')
    assert isinstance(encrypted, str)
    assert encrypted != test_str


def test_get_job_status_and_all_jobs(server_fixture: Server, job_fixture: Job) -> None:
    """Test /supervaizer/jobs/{job_id} and /supervaizer/jobs endpoints."""
    app = server_fixture.app
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test get_job_status (existing job)
    resp = client.get(f"/supervaizer/jobs/{job_fixture.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_fixture.id
    assert "status" in data

    # Test get_job_status (nonexistent job)
    resp = client.get("/supervaizer/jobs/doesnotexist", headers=headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    # Test get_all_jobs
    resp = client.get("/supervaizer/jobs", headers=headers)
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, dict)
    found = False
    for agent_jobs in jobs.values():
        for job in agent_jobs:
            if job["job_id"] == job_fixture.id:
                found = True
    assert found


def test_get_agents_and_agent_details(
    server_fixture: Server, agent_fixture: Agent
) -> None:
    """Test /supervaizer/agents and /supervaizer/agent/{agent_id} endpoints."""
    app = server_fixture.app
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test get_all_agents
    resp = client.get("/supervaizer/agents", headers=headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert isinstance(agents, list)
    assert any(a["id"] == agent_fixture.id for a in agents)

    # Test get_agent_details (existing agent)
    resp = client.get(f"/supervaizer/agent/{agent_fixture.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == agent_fixture.id
    assert data["name"] == agent_fixture.name

    # Test get_agent_details (nonexistent agent)
    resp = client.get("/supervaizer/agent/doesnotexist", headers=headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
