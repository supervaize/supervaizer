# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""FastAPI route generation for DataResource CRUD endpoints.

For each DataResource declared on an Agent, generates routes under:
    GET    /agents/{slug}/data/{resource_name}/            — list
    GET    /agents/{slug}/data/{resource_name}/{item_id}   — detail
    POST   /agents/{slug}/data/{resource_name}/            — create
    PUT    /agents/{slug}/data/{resource_name}/{item_id}   — update
    DELETE /agents/{slug}/data/{resource_name}/{item_id}   — delete
    POST   /agents/{slug}/data/{resource_name}/import/     — CSV bulk import

All routes require the server API key (same auth as existing agent routes).
Uses factory functions per resource to avoid Python closure-in-loop capture bugs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Body, HTTPException, Query, Security
from fastapi.responses import JSONResponse

from supervaizer.common import log
from supervaizer.data_resource import DataResource

if TYPE_CHECKING:
    from supervaizer.agent import Agent
    from supervaizer.server import Server


def create_agent_data_routes(server: "Server", agent: "Agent") -> APIRouter:
    """Generate CRUD REST routes for all DataResources declared on an agent."""
    router = APIRouter(prefix=agent.path, tags=["Data Resources"])
    for resource in agent.data_resources:
        _add_resource_routes(router, resource, server)
    return router


def _add_resource_routes(router: APIRouter, resource: DataResource, server: "Server") -> None:
    """Register all declared operation routes for one DataResource."""
    prefix = f"/data/{resource.name}"

    if resource.on_list is not None:
        router.add_api_route(
            f"{prefix}/",
            _make_list_handler(resource, prefix),
            methods=["GET"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"List {resource.display_name_resolved}",
            operation_id=f"{resource.name}_list",
        )

    if resource.on_get is not None:
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_get_handler(resource, prefix),
            methods=["GET"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"Get {resource.display_name_resolved}",
            operation_id=f"{resource.name}_get",
        )

    if resource.on_create is not None and not resource.read_only:
        router.add_api_route(
            f"{prefix}/",
            _make_create_handler(resource, prefix),
            methods=["POST"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"Create {resource.display_name_resolved}",
            operation_id=f"{resource.name}_create",
        )

    if resource.on_update is not None and not resource.read_only:
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_update_handler(resource, prefix),
            methods=["PUT"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"Update {resource.display_name_resolved}",
            operation_id=f"{resource.name}_update",
        )

    if resource.on_delete is not None and not resource.read_only:
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_delete_handler(resource, prefix),
            methods=["DELETE"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"Delete {resource.display_name_resolved}",
            operation_id=f"{resource.name}_delete",
        )

    if resource.importable and resource.on_import is not None:
        router.add_api_route(
            f"{prefix}/import/",
            _make_import_handler(resource, prefix),
            methods=["POST"],
            dependencies=[Security(server.verify_api_key)],
            summary=f"Import {resource.display_name_resolved} (bulk)",
            operation_id=f"{resource.name}_import",
        )


def _make_list_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        log.info(f"📥 GET {prefix}/ [DataResource list: {r.name}]")
        result = r.on_list()  # type: ignore[misc]
        return result[skip: skip + limit]
    return _handler


def _make_get_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(item_id: str) -> dict[str, Any]:
        log.info(f"📥 GET {prefix}/{item_id} [DataResource get: {r.name}]")
        result = r.on_get(item_id)  # type: ignore[misc]
        if result is None:
            raise HTTPException(status_code=404, detail=f"{r.name} '{item_id}' not found")
        return result
    return _handler


def _make_create_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(data: dict[str, Any] = Body(...)) -> JSONResponse:
        log.info(f"📥 POST {prefix}/ [DataResource create: {r.name}]")
        result = r.on_create(data)  # type: ignore[misc]
        if not isinstance(result, dict) or "id" not in result:
            raise HTTPException(
                status_code=500,
                detail=f"on_create for '{r.name}' must return a dict with 'id'",
            )
        return JSONResponse(content=result, status_code=201)
    return _handler


def _make_update_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(item_id: str, data: dict[str, Any] = Body(...)) -> dict[str, Any]:
        log.info(f"📥 PUT {prefix}/{item_id} [DataResource update: {r.name}]")
        result = r.on_update(item_id, data)  # type: ignore[misc]
        if result is None:
            raise HTTPException(status_code=404, detail=f"{r.name} '{item_id}' not found")
        return result
    return _handler


def _make_delete_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(item_id: str) -> JSONResponse:
        log.info(f"📥 DELETE {prefix}/{item_id} [DataResource delete: {r.name}]")
        success = r.on_delete(item_id)  # type: ignore[misc]
        if not success:
            raise HTTPException(status_code=404, detail=f"{r.name} '{item_id}' not found")
        return JSONResponse(content={"deleted": True}, status_code=200)
    return _handler


def _make_import_handler(r: DataResource, prefix: str) -> Any:
    async def _handler(records: list[dict[str, Any]] = Body(...)) -> dict[str, Any]:
        log.info(f"📥 POST {prefix}/import/ [DataResource import: {r.name}]")
        return r.on_import(records)  # type: ignore[misc]
    return _handler
