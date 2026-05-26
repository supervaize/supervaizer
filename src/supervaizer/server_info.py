# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from supervaizer.common import log
from supervaizer.contracts import API_VERSION
from supervaizer.storage import StorageManager

SERVER_INFO_ID = "server_instance"
SERVER_INFO_KIND = "ServerInfo"


class ServerInfo(BaseModel):
    """Complete server information for storage."""

    id: str = SERVER_INFO_ID
    host: str
    port: int
    api_version: str
    environment: str
    agents: list[dict[str, str]]
    start_time: float
    created_at: str
    updated_at: str


def save_server_info_to_storage(server_instance: Any) -> None:
    """Save server information to storage."""
    try:
        storage = StorageManager()
        server_info = _build_server_info(
            server_instance,
            start_time=time.time(),
        )
        storage.save_object(SERVER_INFO_KIND, server_info.model_dump())
        log.info(
            f"[Server] Server info saved to storage: {server_info.host}:{server_info.port}"
        )
    except Exception as e:
        log.error(f"[Server] Failed to save server info to storage: {e}")


def get_server_info_from_storage() -> ServerInfo | None:
    """Get server information from storage."""
    storage = StorageManager()
    server_data = storage.get_object_by_id(SERVER_INFO_KIND, SERVER_INFO_ID)
    if server_data:
        return ServerInfo.model_validate(server_data)
    return None


def get_server_info_from_live(server_instance: Any) -> ServerInfo:
    """Build server information from a live server instance."""
    return _build_server_info(
        server_instance,
        start_time=getattr(server_instance, "_start_time", time.time()),
    )


def _build_server_info(server_instance: Any, *, start_time: float) -> ServerInfo:
    timestamp = datetime.now().isoformat()
    return ServerInfo(
        id=SERVER_INFO_ID,
        host=getattr(server_instance, "host", "N/A"),
        port=getattr(server_instance, "port", 0),
        api_version=API_VERSION,
        environment=os.getenv("SUPERVAIZER_ENVIRONMENT", "development"),
        agents=_build_agent_info(server_instance),
        start_time=start_time,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _build_agent_info(server_instance: Any) -> list[dict[str, str]]:
    agents = getattr(server_instance, "agents", None)
    if not agents:
        return []
    return [
        {
            "name": agent.name,
            "description": agent.description,
            "version": agent.version,
            "api_path": agent.path,
            "slug": agent.slug,
            "instructions_path": agent.instructions_path,
        }
        for agent in agents
    ]
