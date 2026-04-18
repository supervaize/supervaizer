# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for _extract_client_ip and TRUSTED_PROXIES handling."""

from unittest.mock import patch

import pytest

from supervaizer.access.client_ip import TRUSTED_PROXIES, _extract_client_ip


def _make_scope(peer_ip: str, xff: str = "") -> dict:
    """Build a minimal ASGI scope dict."""
    headers = []
    if xff:
        headers.append((b"x-forwarded-for", xff.encode()))
    return {
        "type": "http",
        "client": (peer_ip, 12345),
        "headers": headers,
    }


class TestExtractClientIpNoTrustedProxies:
    """When TRUSTED_PROXIES is empty, always return the direct peer."""

    def test_returns_peer_ip(self) -> None:
        scope = _make_scope("1.2.3.4")
        assert _extract_client_ip(scope) == "1.2.3.4"

    def test_ignores_xff_when_no_trusted_proxies(self) -> None:
        scope = _make_scope("1.2.3.4", xff="9.9.9.9, 8.8.8.8")
        assert _extract_client_ip(scope) == "1.2.3.4"

    def test_missing_client_returns_empty(self) -> None:
        scope = {"type": "http", "client": None, "headers": []}
        assert _extract_client_ip(scope) == ""

    def test_empty_peer_returns_empty(self) -> None:
        scope = {"type": "http", "client": ("", 0), "headers": []}
        assert _extract_client_ip(scope) == ""

    def test_malformed_peer_returns_empty(self) -> None:
        scope = _make_scope("not-an-ip")
        assert _extract_client_ip(scope) == ""


class TestExtractClientIpWithTrustedProxies:
    """When peer is in TRUSTED_PROXIES, use leftmost XFF entry."""

    @pytest.fixture(autouse=True)
    def patch_trusted_proxies(self):
        import ipaddress

        trusted = [ipaddress.ip_network("10.0.0.0/8")]
        with patch("supervaizer.access.client_ip.TRUSTED_PROXIES", trusted):
            yield

    def test_peer_in_trusted_cidr_uses_xff(self) -> None:
        scope = _make_scope("10.0.0.1", xff="203.0.113.5, 10.0.0.1")
        assert _extract_client_ip(scope) == "203.0.113.5"

    def test_peer_not_in_trusted_cidr_ignores_xff(self) -> None:
        scope = _make_scope("1.2.3.4", xff="9.9.9.9")
        assert _extract_client_ip(scope) == "1.2.3.4"

    def test_trusted_peer_no_xff_returns_peer(self) -> None:
        scope = _make_scope("10.0.0.2")
        assert _extract_client_ip(scope) == "10.0.0.2"

    def test_trusted_peer_malformed_xff_falls_back_to_peer(self) -> None:
        scope = _make_scope("10.0.0.1", xff="not-an-ip, 10.0.0.1")
        assert _extract_client_ip(scope) == "10.0.0.1"

    def test_trusted_peer_empty_xff_returns_peer(self) -> None:
        scope = _make_scope("10.0.0.5", xff="  ")
        assert _extract_client_ip(scope) == "10.0.0.5"
