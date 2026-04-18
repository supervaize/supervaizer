# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for require_api_key and require_scope dependencies."""

import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def _make_app(required_scope: str | None = None) -> FastAPI:
    """Build a test app with optional scope enforcement."""
    from supervaizer.access.api_auth import require_api_key, require_scope

    app = FastAPI()

    if required_scope:
        dep = Depends(require_scope(required_scope))
    else:
        dep = Depends(require_api_key)

    @app.get("/guarded", dependencies=[dep])
    def guarded() -> dict:
        return {"ok": True}

    return app


class TestRequireApiKey:
    """Tests for require_api_key."""

    def test_missing_header_returns_401(self) -> None:
        app = _make_app()
        client = TestClient(app)
        response = client.get("/guarded")
        assert response.status_code == 401
        assert "API key" in response.json()["detail"]

    def test_unknown_key_returns_401(self) -> None:
        app = _make_app()
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "not-in-registry"})
        assert response.status_code == 401

    def test_known_read_key_passes(self) -> None:
        app = _make_app()
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_123"})
        assert response.status_code == 200

    def test_known_write_key_passes(self) -> None:
        app = _make_app()
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_456"})
        assert response.status_code == 200

    def test_env_key_preloaded_as_write(self) -> None:
        """SUPERVAIZER_API_KEY env var should be in API_KEYS with write scope."""
        from supervaizer.access.api_auth import API_KEYS

        env_key = os.getenv("SUPERVAIZER_API_KEY", "").strip()
        if env_key:
            assert env_key in API_KEYS
            assert API_KEYS[env_key]["scope"] == "write"

    def test_live_server_key_fallback(self) -> None:
        """Key matching app.state.server.api_key is accepted even if not in API_KEYS."""
        from fastapi import FastAPI
        from supervaizer.access.api_auth import require_api_key

        app = FastAPI()
        mock_server = type("S", (), {"api_key": "live-server-secret"})()
        app.state.server = mock_server

        @app.get("/guarded", dependencies=[Depends(require_api_key)])
        def guarded() -> dict:
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "live-server-secret"})
        assert response.status_code == 200


class TestRequireScope:
    """Tests for require_scope — hierarchical scope model."""

    def test_read_key_on_read_scope_passes(self) -> None:
        app = _make_app(required_scope="read")
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_123"})
        assert response.status_code == 200

    def test_write_key_satisfies_read_scope(self) -> None:
        """write scope implies read — hierarchical."""
        app = _make_app(required_scope="read")
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_456"})
        assert response.status_code == 200

    def test_read_key_on_write_scope_returns_403(self) -> None:
        """read scope is insufficient for write-required endpoints."""
        app = _make_app(required_scope="write")
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_123"})
        assert response.status_code == 403
        assert "scope" in response.json()["detail"].lower()

    def test_write_key_on_write_scope_passes(self) -> None:
        app = _make_app(required_scope="write")
        client = TestClient(app)
        response = client.get("/guarded", headers={"X-API-Key": "key_456"})
        assert response.status_code == 200

    def test_missing_key_on_write_scope_returns_401(self) -> None:
        app = _make_app(required_scope="write")
        client = TestClient(app)
        response = client.get("/guarded")
        assert response.status_code == 401
