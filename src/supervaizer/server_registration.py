# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import Any

from cryptography.hazmat.primitives import serialization

from supervaizer.__version__ import VERSION
from supervaizer.contracts import API_VERSION, controller_contract_info


def build_server_registration_info(server: Any) -> dict[str, Any]:
    """Build the Studio-compatible server.register payload details."""
    assert server.public_key is not None, "Public key not initialized"
    contract = controller_contract_info()
    return {
        "server_id": server.server_id,
        "url": server.public_url,
        "uri": server.uri,
        "api_version": API_VERSION,
        "controller_version": VERSION,
        **contract,
        "environment": server.environment,
        "public_key": str(
            server.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
        ),
        "api_key": server.api_key,
        "docs": {
            "swagger": f"{server.public_url}{server.app.docs_url}",
            "redoc": f"{server.public_url}{server.app.redoc_url}",
            "openapi": f"{server.public_url}{server.app.openapi_url}",
        },
        "agents": [agent.registration_info for agent in server.agents],
    }
