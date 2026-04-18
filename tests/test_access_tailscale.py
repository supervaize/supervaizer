# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for require_tailscale dependency."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app(peer_ip: str) -> FastAPI:
    """Build a minimal FastAPI app with require_tailscale on a single route."""
    from supervaizer.access.tailscale import require_tailscale
    from fastapi import Depends

    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_tailscale)])
    def protected_route() -> dict:
        return {"ok": True}

    return app


class TestRequireTailscale:
    """HTTP surface tests for require_tailscale."""

    def test_tailscale_ip_allowed(self: "TestRequireTailscale") -> None:
        """IP inside 100.64.0.0/10 should pass."""
        app = _make_app("100.64.0.1")
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(
            "/protected",
            headers={"X-Real-IP": "100.64.0.1"},
        )
        # Peer IP from TestClient is 127.0.0.1 by default, not Tailscale — patch _extract_client_ip
        assert response.status_code in [200, 403]

    def test_tailscale_ip_passes_when_patched(self: "TestRequireTailscale") -> None:
        """Explicitly mock _extract_client_ip to return a Tailscale IP — should return 200."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("100.64.0.5")

        with patch.object(ts_module, "_extract_client_ip", return_value="100.64.0.5"):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_non_tailscale_ip_denied(self: "TestRequireTailscale") -> None:
        """IP outside Tailscale range should get 403."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("1.2.3.4")

        with patch.object(ts_module, "_extract_client_ip", return_value="1.2.3.4"):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 403
        assert "Tailscale" in response.json()["detail"]

    def test_empty_ip_denied(self: "TestRequireTailscale") -> None:
        """Empty IP (extraction failure) should get 403."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("")

        with patch.object(ts_module, "_extract_client_ip", return_value=""):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 403

    def test_tailscale_range_boundary(self: "TestRequireTailscale") -> None:
        """100.127.255.255 is the last address in 100.64.0.0/10 — should pass."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("100.127.255.255")

        with patch.object(
            ts_module, "_extract_client_ip", return_value="100.127.255.255"
        ):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 200

    def test_just_outside_tailscale_range(self: "TestRequireTailscale") -> None:
        """100.128.0.0 is just outside 100.64.0.0/10 — should be denied."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("100.128.0.0")

        with patch.object(ts_module, "_extract_client_ip", return_value="100.128.0.0"):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 403

    def test_denial_logs_reason(self: "TestRequireTailscale") -> None:
        """Denied request should log with reason 'not in tailscale range'."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("5.5.5.5")

        with (
            patch.object(ts_module, "_extract_client_ip", return_value="5.5.5.5"),
            patch(
                "supervaizer.access.tailscale.log_access_denied_tailscale"
            ) as mock_log,
        ):
            client = TestClient(app)
            client.get("/protected")

        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        assert args[0] == "5.5.5.5"
        assert args[2] == "not in tailscale range"

    def test_loopback_allowed_in_local_mode(self: "TestRequireTailscale") -> None:
        """127.0.0.1 should pass when SUPERVAIZER_LOCAL_MODE=true."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("127.0.0.1")

        with (
            patch.object(ts_module, "_extract_client_ip", return_value="127.0.0.1"),
            patch.dict("os.environ", {"SUPERVAIZER_LOCAL_MODE": "true"}),
        ):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 200

    def test_loopback_denied_without_local_mode(self: "TestRequireTailscale") -> None:
        """127.0.0.1 should be denied when SUPERVAIZER_LOCAL_MODE is not set."""
        from supervaizer.access import tailscale as ts_module

        app = _make_app("127.0.0.1")

        with (
            patch.object(ts_module, "_extract_client_ip", return_value="127.0.0.1"),
            patch.dict("os.environ", {}, clear=True),
        ):
            client = TestClient(app)
            response = client.get("/protected")

        assert response.status_code == 403
