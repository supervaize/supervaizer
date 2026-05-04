# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for admin routes module to improve coverage."""

import time
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from supervaizer.admin.routes import (  # <-- MODIFIED: removed generate_console_token, validate_console_token, verify_admin_access
    AdminStats,
    ServerConfiguration,
    ServerStatus,
    add_log_to_queue,
    create_admin_routes,
    format_uptime,
    get_dashboard_stats,
    get_server_configuration,
    get_server_status,
    process_console_command,
    set_server_start_time,
)
from supervaizer.common import ApiError, ApiSuccess

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from supervaizer.storage import StorageManager


class TestAdminUtilityFunctions:
    """Tests for admin utility functions."""

    def test_format_uptime_days(self) -> None:
        """Test format_uptime with days."""
        result = format_uptime(90061)  # 1 day, 1 hour, 1 minute, 1 second
        assert result == "1d 1h 1m"

    def test_format_uptime_hours(self) -> None:
        """Test format_uptime with hours."""
        result = format_uptime(3661)  # 1 hour, 1 minute, 1 second
        assert result == "1h 1m"

    def test_format_uptime_minutes(self) -> None:
        """Test format_uptime with minutes only."""
        result = format_uptime(61)  # 1 minute, 1 second
        assert result == "1m"

    def test_format_uptime_zero(self) -> None:
        """Test format_uptime with zero seconds."""
        result = format_uptime(0)
        assert result == "0m"

    def test_set_server_start_time(self) -> None:
        """Test setting server start time."""
        test_time = time.time()
        set_server_start_time(test_time)
        # We can't easily test this without accessing globals, but we can verify it doesn't crash
        assert True

    def test_add_log_to_queue(self) -> None:
        """Test adding log message to queue."""
        # This function uses a global queue, so we just test it doesn't crash
        add_log_to_queue("2023-01-01 10:00:00", "INFO", "Test message")
        assert True

    # <-- REMOVED: test_generate_console_token, test_validate_console_token_*
    # (console token system removed; Tailscale is the gate)


class TestAdminModels:
    """Tests for admin data models."""

    def test_admin_stats_model(self) -> None:
        """Test AdminStats model creation."""
        stats = AdminStats(
            jobs={"active": 5, "completed": 10},
            cases={"open": 3, "closed": 7},
            collections=2,
        )
        assert stats.jobs["active"] == 5
        assert stats.cases["open"] == 3
        assert stats.collections == 2

    def test_server_status_model(self) -> None:
        """Test ServerStatus model creation."""
        status = ServerStatus(
            status="running",
            uptime="1h 30m",
            uptime_seconds=5400,
            memory_usage="256 MB",
            memory_usage_mb=256.0,
            memory_percent=15.5,
            cpu_percent=12.3,
            active_connections=5,
            agents_count=2,
            host="localhost",
            port=8001,
            environment="test",
            database_type="sqlite",
            storage_path="/tmp/test.db",
        )
        assert status.status == "running"
        assert status.uptime_seconds == 5400
        assert status.memory_usage_mb == 256.0

    def test_server_configuration_model(self) -> None:
        """Test ServerConfiguration model creation."""
        config = ServerConfiguration(
            host="localhost",
            port=8001,
            api_version="1.0.0",
            environment="test",
            database_type="sqlite",
            storage_path="/tmp/test.db",
            agents=[{"name": "test-agent", "version": "1.0.0"}],
        )
        assert config.host == "localhost"
        assert config.port == 8001
        assert len(config.agents) == 1


# <-- REMOVED: TestAdminAuthentication class
# (verify_admin_access removed; Tailscale is the gate; see test_access_tailscale.py)


class TestAdminDataFunctions:
    """Tests for admin data retrieval functions."""

    def test_get_server_status(self, mocker: "MockerFixture") -> None:
        """Test getting server status."""
        # Mock server info
        mock_server_info = Mock()
        mock_server_info.host = "localhost"
        mock_server_info.port = 8001
        mock_server_info.environment = "test"
        mock_server_info.start_time = time.time() - 3600  # 1 hour ago
        mock_server_info.storage.database_type = "sqlite"
        mock_server_info.storage.storage_path = "/tmp/test.db"
        mock_server_info.agents = [Mock(), Mock()]  # 2 agents

        # Patch the import inside the function
        mocker.patch(
            "supervaizer.server.get_server_info_from_storage",
            return_value=mock_server_info,
        )

        # Mock psutil functions
        mock_memory = Mock()
        mock_memory.percent = 75.5
        mocker.patch("psutil.virtual_memory", return_value=mock_memory)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 256 * 1024 * 1024  # 256 MB
        mocker.patch("psutil.Process", return_value=mock_process)

        mocker.patch("psutil.cpu_percent", return_value=12.3)
        mocker.patch("psutil.net_connections", return_value=[1, 2, 3, 4, 5])

        status = get_server_status()

        assert isinstance(status, ServerStatus)
        assert status.host == "localhost"
        assert status.port == 8001
        assert status.environment == "test"
        assert status.agents_count == 2
        assert status.memory_percent == 75.5
        assert status.cpu_percent == 12.3
        assert status.active_connections == 5

    def test_get_server_status_no_server_info(self, mocker: "MockerFixture") -> None:
        """Test getting server status when server info is not available."""
        mocker.patch(
            "supervaizer.server.get_server_info_from_storage", return_value=None
        )

        with pytest.raises(HTTPException) as exc_info:
            get_server_status()

        assert exc_info.value.status_code == 503
        assert "Server information not available" in exc_info.value.detail

    def test_get_server_configuration(self, storage_manager: "StorageManager") -> None:
        """Test getting server configuration."""
        # Mock server info
        mock_server_info = Mock()
        mock_server_info.host = "localhost"
        mock_server_info.port = 8001
        mock_server_info.environment = "test"
        mock_server_info.api_version = "1.0.0"  # Use real string, not mock
        mock_server_info.storage.database_type = "sqlite"
        mock_server_info.storage.storage_path = "/tmp/test.db"

        # Create real dictionary agents instead of Mock objects
        agent1_dict = {"name": "agent1", "version": "1.0.0"}
        agent2_dict = {"name": "agent2", "version": "2.0.0"}
        mock_server_info.agents = [agent1_dict, agent2_dict]  # Use actual dictionaries

        with patch(
            "supervaizer.server.get_server_info_from_storage",
            return_value=mock_server_info,
        ):
            config = get_server_configuration(storage_manager)

        assert isinstance(config, ServerConfiguration)
        assert config.host == "localhost"
        assert config.port == 8001
        assert config.environment == "test"
        assert config.api_version == "1.0.0"
        assert len(config.agents) == 2
        assert config.agents[0]["name"] == "agent1"
        assert config.agents[1]["version"] == "2.0.0"

    def test_get_dashboard_stats(self, storage_manager: "StorageManager") -> None:
        """Test getting dashboard statistics."""
        # Mock storage data
        mock_jobs = [
            {"status": "in_progress"},
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed"},
        ]
        mock_cases = [
            {"status": "in_progress"},
            {"status": "completed"},
            {"status": "failed"},
        ]

        storage_manager.get_objects = Mock(
            side_effect=lambda obj_type: (
                mock_jobs
                if obj_type == "Job"
                else mock_cases
                if obj_type == "Case"
                else []
            )
        )

        # Mock TinyDB tables
        mock_db = Mock()
        mock_db.tables.return_value = ["Job", "Case"]
        storage_manager._db = mock_db

        stats = get_dashboard_stats(storage_manager)

        assert isinstance(stats, AdminStats)
        assert stats.jobs["total"] == 4
        assert stats.jobs["running"] == 1
        assert stats.jobs["completed"] == 2
        assert stats.jobs["failed"] == 1
        assert stats.cases["total"] == 3
        assert stats.cases["running"] == 1
        assert stats.cases["completed"] == 1
        assert stats.cases["failed"] == 1
        assert stats.collections == 2


class TestConsoleCommands:
    """Tests for console command processing."""

    @pytest.mark.asyncio
    async def test_process_console_command_help(self) -> None:
        """Test processing help command."""
        result = await process_console_command("help")

        assert isinstance(result, dict)
        assert "message" in result
        assert "level" in result
        assert result["level"] == "INFO"
        assert "Available commands" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_status(self) -> None:
        """Test processing status command."""
        result = await process_console_command("status")

        assert isinstance(result, dict)
        assert result["level"] == "INFO"
        assert "Server is running" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_server_info(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test processing server-info command."""
        # Mock server status
        mock_status = Mock()
        mock_status.status = "running"
        mock_status.uptime = "1h 30m"
        mock_status.cpu_percent = 15.5
        mock_status.memory_usage = "256 MB"

        mocker.patch(
            "supervaizer.admin.routes.get_server_status", return_value=mock_status
        )

        result = await process_console_command("server-info")

        assert isinstance(result, dict)
        assert result["level"] == "INFO"
        assert "running" in result["message"]
        assert "1h 30m" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_memory(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test processing memory command."""
        mock_status = Mock()
        mock_status.memory_usage = "256 MB"
        mock_status.memory_percent = 65.5

        mocker.patch(
            "supervaizer.admin.routes.get_server_status", return_value=mock_status
        )

        result = await process_console_command("memory")

        assert isinstance(result, dict)
        assert result["level"] == "INFO"
        assert "256 MB" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_uptime(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test processing uptime command."""
        mock_status = Mock()
        mock_status.uptime = "2h 15m"
        mock_status.uptime_seconds = 8100

        mocker.patch(
            "supervaizer.admin.routes.get_server_status", return_value=mock_status
        )

        result = await process_console_command("uptime")

        assert isinstance(result, dict)
        assert result["level"] == "INFO"
        assert "2h 15m" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_debug(self, mocker: "MockerFixture") -> None:
        """Test processing debug command."""
        mocker.patch.dict("os.environ", {"SUPERVAIZER_ENVIRONMENT": "test"})

        result = await process_console_command("debug")

        assert isinstance(result, dict)
        assert result["level"] == "DEBUG"
        assert "test" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_clear(self) -> None:
        """Test processing clear command."""
        result = await process_console_command("clear")

        assert isinstance(result, dict)
        assert result["level"] == "SYSTEM"
        assert result["message"] == "Console cleared"

    @pytest.mark.asyncio
    async def test_process_console_command_test_log(self) -> None:
        """Test processing test-log command."""
        result = await process_console_command("test-log")

        assert isinstance(result, dict)
        assert result["level"] == "SUCCESS"
        assert "Test log message sent" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_unknown(self) -> None:
        """Test processing unknown command."""
        result = await process_console_command("unknown_command")

        assert isinstance(result, dict)
        assert result["level"] == "ERROR"
        assert "Unknown command" in result["message"]

    @pytest.mark.asyncio
    async def test_process_console_command_empty(self) -> None:
        """Test processing empty command."""
        result = await process_console_command("")

        assert isinstance(result, dict)
        # Empty command falls through to unknown command case
        assert result["level"] == "ERROR"


class TestAdminRoutesIntegration:
    """Integration tests for admin routes using TestClient."""

    @pytest.fixture
    def client(self, mocker: "MockerFixture") -> TestClient:
        """Create test client with admin routes mounted at /manage (no auth deps here)."""
        mock_server_info = Mock()
        mock_server_info.host = "localhost"
        mock_server_info.port = 8001
        mock_server_info.environment = "test"
        mock_server_info.api_version = "1.0.0"
        mock_server_info.start_time = time.time() - 3600
        mock_server_info.storage.database_type = "sqlite"
        mock_server_info.storage.storage_path = "/tmp/test.db"
        mock_server_info.agents = []

        mocker.patch(
            "supervaizer.server.get_server_info_from_storage",
            return_value=mock_server_info,
        )

        mock_memory = Mock()
        mock_memory.percent = 50.0
        mocker.patch("psutil.virtual_memory", return_value=mock_memory)

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 128 * 1024 * 1024
        mocker.patch("psutil.Process", return_value=mock_process)

        mocker.patch("psutil.cpu_percent", return_value=10.5)
        mocker.patch("psutil.net_connections", return_value=[1, 2, 3])

        mocker.patch("supervaizer.admin.routes.API_VERSION", "1.0.0")

        mock_storage = Mock()
        mock_storage.get_objects.side_effect = lambda obj_type: []
        mock_db = Mock()
        mock_db.tables.return_value = []
        mock_storage._db = mock_db
        mock_storage.db_path = Mock()
        mock_storage.db_path.absolute.return_value = "/tmp/test.db"

        mocker.patch(
            "supervaizer.admin.routes.StorageManager", return_value=mock_storage
        )

        router = create_admin_routes()

        from fastapi import FastAPI

        app = FastAPI()
        # <-- MODIFIED: prefix="/manage" matches private_router; no auth dep in create_admin_routes()
        app.include_router(router, prefix="/manage")

        return TestClient(app)

    def test_admin_dashboard(self, client: TestClient) -> None:
        """Test admin dashboard — Tailscale gate is at router level, not here."""
        response = client.get("/manage/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Dashboard" in response.text or "Supervaizer" in response.text

    def test_admin_jobs_page(self, client: TestClient) -> None:
        """Test admin jobs page."""
        response = client.get("/manage/jobs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_cases_page(self, client: TestClient) -> None:
        """Test admin cases page."""
        response = client.get("/manage/cases")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_server_page(self, client: TestClient) -> None:
        """Test admin server page."""
        response = client.get("/manage/server")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_agents_page(self, client: TestClient) -> None:
        """Test admin agents page."""
        response = client.get("/manage/agents")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_console_page(self, client: TestClient) -> None:
        """Test admin console page."""
        response = client.get("/manage/console")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_stats(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test API stats endpoint."""
        mock_jobs = [{"status": "completed"}, {"status": "failed"}]
        mock_cases = [{"status": "completed"}]

        with patch(
            "supervaizer.server.get_server_info_from_storage"
        ) as mock_get_server:
            mock_storage = Mock()
            mock_storage.get_objects.side_effect = lambda obj_type: (
                mock_jobs
                if obj_type == "Job"
                else mock_cases
                if obj_type == "Case"
                else []
            )
            mock_db = Mock()
            mock_db.tables.return_value = ["Job", "Case"]
            mock_storage._db = mock_db
            mock_get_server.return_value.storage = mock_storage

            response = client.get("/manage/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "cases" in data
        assert "collections" in data

    def test_api_server_status(self, client: TestClient) -> None:
        """Test API server status endpoint."""
        response = client.get("/manage/api/server/status")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_server_register_success(self, mocker: "MockerFixture") -> None:
        """Server register endpoint awaits supervisor registration and returns success."""
        from fastapi import FastAPI

        supervisor_account = Mock()
        supervisor_account.register_server = mocker.AsyncMock(
            return_value=ApiSuccess(
                message="Event SERVER_REGISTER sent",
                detail={"id": "evt-1"},
            )
        )
        server = Mock()
        server.supervisor_account = supervisor_account

        app = FastAPI()
        app.state.server = server
        app.include_router(create_admin_routes(), prefix="/manage")
        client = TestClient(app)

        response = client.post("/manage/api/server/register")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Event SERVER_REGISTER sent",
            "detail": {"id": "evt-1"},
        }
        supervisor_account.register_server.assert_awaited_once_with(server=server)

    def test_api_server_register_requires_supervisor_account(self) -> None:
        """Registration endpoint returns 503 when no supervisor account is configured."""
        from fastapi import FastAPI

        server = Mock()
        server.supervisor_account = None
        app = FastAPI()
        app.state.server = server
        app.include_router(create_admin_routes(), prefix="/manage")
        client = TestClient(app)

        response = client.post("/manage/api/server/register")

        assert response.status_code == 503
        assert response.json()["detail"] == "No supervisor account configured"

    def test_api_server_register_returns_502_for_api_error(
        self, mocker: "MockerFixture"
    ) -> None:
        """Registration endpoint surfaces non-success API results as 502."""
        from fastapi import FastAPI

        supervisor_account = Mock()
        supervisor_account.register_server = mocker.AsyncMock(
            return_value=ApiError(message="register failed", detail={"error": "bad"})
        )
        server = Mock()
        server.supervisor_account = supervisor_account

        app = FastAPI()
        app.state.server = server
        app.include_router(create_admin_routes(), prefix="/manage")
        client = TestClient(app)

        response = client.post("/manage/api/server/register")

        assert response.status_code == 502
        assert response.json() == {
            "success": False,
            "message": "register failed",
            "detail": {"error": "bad"},
        }

    def test_api_agents(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test API agents endpoint."""
        mock_agent = Mock()
        mock_agent.get = Mock(
            side_effect=lambda key, default="": {
                "name": "test-agent",
                "description": "Test agent",
                "type": "conversational",
            }.get(key, default)
        )

        with patch(
            "supervaizer.server.get_server_info_from_storage"
        ) as mock_get_server:
            mock_get_server.return_value.agents = [mock_agent]

            response = client.get("/manage/api/agents")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_test_log_endpoint(self, client: TestClient) -> None:
        """Test the test log endpoint."""
        response = client.get("/manage/test-log")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Test log added to queue"

    def test_api_jobs_basic(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test basic jobs API endpoint."""
        mock_job_repo = Mock()
        mock_job_repo.list_jobs.return_value = []
        mock_job_repo.count_jobs.return_value = 0

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )

        response = client.get("/manage/api/jobs")
        assert response.status_code in [200, 500]

    def test_api_jobs_with_filters(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test jobs API with status filter."""
        mock_job_repo = Mock()
        mock_job_repo.list_jobs.return_value = []
        mock_job_repo.count_jobs.return_value = 0

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )

        response = client.get("/manage/api/jobs?status=completed")
        assert response.status_code in [200, 500]

    def test_api_job_details_not_found(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test job details API with non-existent job."""
        mock_job_repo = Mock()
        mock_job_repo.get_job.return_value = None

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )

        response = client.get("/manage/api/jobs/nonexistent")
        assert response.status_code in [404, 500]

    def test_api_cases_basic(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test basic cases API endpoint."""
        mock_case_repo = Mock()
        mock_case_repo.list_cases.return_value = []
        mock_case_repo.count_cases.return_value = 0

        mocker.patch(
            "supervaizer.storage.create_case_repository", return_value=mock_case_repo
        )

        response = client.get("/manage/api/cases")
        assert response.status_code in [200, 500]

    def test_api_case_details_not_found(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test case details API with non-existent case."""
        mock_case_repo = Mock()
        mock_case_repo.get_case.return_value = None

        mocker.patch(
            "supervaizer.storage.create_case_repository", return_value=mock_case_repo
        )

        response = client.get("/manage/api/cases/nonexistent")
        assert response.status_code in [404, 500]

    def test_update_job_status(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test updating job status."""
        mock_job_repo = Mock()
        mock_job_repo.update_job_status.return_value = True

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )

        response = client.post(
            "/manage/api/jobs/job1/status",
            json={"status": "completed"},
        )
        assert response.status_code in [200, 400, 403, 500]

    def test_update_case_status(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test updating case status."""
        mock_case_repo = Mock()
        mock_case_repo.update_case_status.return_value = True

        mocker.patch(
            "supervaizer.storage.create_case_repository", return_value=mock_case_repo
        )

        response = client.post(
            "/manage/api/cases/case1/status",
            json={"status": "closed"},
        )
        assert response.status_code in [200, 400, 403, 500]

    def test_delete_job(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test deleting a job."""
        mock_job_repo = Mock()
        mock_job_repo.delete_job.return_value = True

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )

        response = client.delete("/manage/api/jobs/job1")
        assert response.status_code in [200, 403, 500]

    def test_delete_case(self, client: TestClient, mocker: "MockerFixture") -> None:
        """Test deleting a case."""
        mock_case_repo = Mock()
        mock_case_repo.delete_case.return_value = True

        mocker.patch(
            "supervaizer.storage.create_case_repository", return_value=mock_case_repo
        )

        response = client.delete("/manage/api/cases/case1")
        assert response.status_code in [200, 403, 500]

    def test_api_recent_activity(
        self, client: TestClient, mocker: "MockerFixture"
    ) -> None:
        """Test recent activity API endpoint."""
        mock_job_repo = Mock()
        mock_case_repo = Mock()
        mock_job_repo.list_jobs.return_value = []
        mock_case_repo.list_cases.return_value = []

        mocker.patch(
            "supervaizer.storage.create_job_repository", return_value=mock_job_repo
        )
        mocker.patch(
            "supervaizer.storage.create_case_repository", return_value=mock_case_repo
        )

        response = client.get("/manage/api/recent-activity")
        assert response.status_code in [200, 500]

    def test_console_execute(self, client: TestClient) -> None:
        """Test console command execution — no token required; Tailscale is the gate."""
        response = client.post(
            "/manage/api/console/execute",
            json={"command": "help"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_debug_endpoints(self, client: TestClient) -> None:
        """Test debug endpoints."""
        # <-- MODIFIED: debug-tokens removed; only debug-queue and test-loguru remain
        response = client.get("/manage/debug-queue")
        assert response.status_code == 200
        data = response.json()
        assert "queue_size_before" in data

        response = client.get("/manage/test-loguru")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Loguru test messages sent"
