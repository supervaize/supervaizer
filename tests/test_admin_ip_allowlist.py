# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for admin IP allowlist (ADMIN_ALLOWED_IPS)."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from supervaizer.admin.ip_allowlist import (
    AdminIPAllowlistMiddleware,
    client_ip_is_allowed,
    get_effective_client_ip,
    is_admin_url_path,
)


class TestIsAdminUrlPath:
    def test_admin_root(self) -> None:
        assert is_admin_url_path("/admin") is True

    def test_admin_nested(self) -> None:
        assert is_admin_url_path("/admin/jobs") is True

    def test_not_administrator(self) -> None:
        assert is_admin_url_path("/administrator") is False


class TestClientIpIsAllowed:
    def test_empty_env_allows_any(self) -> None:
        assert client_ip_is_allowed("1.2.3.4", "") is True
        assert client_ip_is_allowed("1.2.3.4", "   ") is True

    def test_exact_match(self) -> None:
        assert client_ip_is_allowed("192.168.1.10", "192.168.1.10") is True
        assert client_ip_is_allowed("192.168.1.10", "192.168.1.11") is False

    def test_cidr(self) -> None:
        assert client_ip_is_allowed("10.0.0.5", "10.0.0.0/8") is True
        assert client_ip_is_allowed("192.168.0.1", "10.0.0.0/8") is False

    def test_multiple_entries(self) -> None:
        raw = "192.168.1.1, 10.0.0.0/8"
        assert client_ip_is_allowed("192.168.1.1", raw) is True
        assert client_ip_is_allowed("10.5.5.5", raw) is True
        assert client_ip_is_allowed("172.16.0.1", raw) is False


class TestGetEffectiveClientIp:
    def test_prefers_x_forwarded_for_first(self) -> None:
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.1, 198.51.100.2"),
            ],
            "client": ("testclient", 12345),
        }
        req = Request(scope)
        assert get_effective_client_ip(req) == "203.0.113.1"

    def test_fallback_client(self) -> None:
        scope = {
            "type": "http",
            "headers": [],
            "client": ("198.51.100.9", 12345),
        }
        req = Request(scope)
        assert get_effective_client_ip(req) == "198.51.100.9"


@pytest.fixture
def minimal_admin_app(monkeypatch):
    """FastAPI app with admin router + IP middleware (no live server)."""
    monkeypatch.setenv("SUPERVAIZER_API_KEY", "test-api-key")

    from unittest.mock import patch

    from supervaizer.admin.routes import create_admin_routes

    mock_storage = Mock()
    mock_storage.get_objects.side_effect = lambda obj_type: []
    mock_db = Mock()
    mock_db.tables.return_value = []
    mock_storage._db = mock_db
    mock_storage.db_path = Mock()
    mock_storage.db_path.absolute.return_value = "/tmp/test.db"

    app = FastAPI()
    app.add_middleware(AdminIPAllowlistMiddleware)
    server = Mock()
    server.agents = []
    server.api_key = "test-api-key"
    server.supervisor_account = "x"
    app.state.server = server

    with patch("supervaizer.admin.routes.StorageManager", return_value=mock_storage):
        app.include_router(create_admin_routes(), prefix="/admin")

    return app


class TestAdminIPAllowlistMiddleware:
    def test_empty_ADMIN_ALLOWED_IPS_allows_all(
        self, minimal_admin_app, monkeypatch
    ) -> None:
        monkeypatch.delenv("ADMIN_ALLOWED_IPS", raising=False)
        client = TestClient(minimal_admin_app)
        r = client.get("/admin/api/stats")
        assert r.status_code == 200

    def test_blocks_when_not_in_list(self, minimal_admin_app, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_ALLOWED_IPS", "203.0.113.2")
        client = TestClient(minimal_admin_app)
        r = client.get(
            "/admin/api/stats",
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert r.status_code == 403
        assert "client IP" in r.json()["detail"]

    def test_allows_when_in_list(self, minimal_admin_app, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_ALLOWED_IPS", "203.0.113.1")
        client = TestClient(minimal_admin_app)
        r = client.get(
            "/admin/api/stats",
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert r.status_code == 200

    def test_non_admin_paths_unaffected(self, minimal_admin_app, monkeypatch) -> None:
        monkeypatch.setenv("ADMIN_ALLOWED_IPS", "203.0.113.2")
        client = TestClient(minimal_admin_app)
        r = client.get("/openapi.json")
        assert r.status_code == 200
