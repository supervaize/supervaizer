# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
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

import inspect
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
)  # <-- MODIFIED: removed Security, added Depends
from fastapi.responses import JSONResponse

from supervaizer.access import require_scope  # <-- ADDED
from supervaizer.common import log
from supervaizer.contracts import V2WorkspaceContext
from supervaizer.data_resource import DataResource, DataResourceContext
from supervaizer.workspace_authorization import (
    WorkspaceAuthorizationError,
    extract_workspace_authorization_token,
    verify_workspace_authorization_for_request,
)

if TYPE_CHECKING:
    from supervaizer.agent import Agent
    from supervaizer.server import Server


def create_agent_data_routes(server: Server, agent: Agent) -> APIRouter:
    """Generate CRUD REST routes for all DataResources declared on an agent."""
    router = APIRouter(prefix=agent.path, tags=["Data Resources"])
    agent_slug = agent.slug
    for resource in agent.data_resources:
        _add_resource_routes(router, resource, agent_slug, server)
    return router


def _data_resource_operation_id(
    agent_slug: str, resource_name: str, action: str
) -> str:
    """Build a globally unique OpenAPI operation_id (per app, all agents)."""
    return f"{agent_slug}_{resource_name}_{action}"


def _add_resource_routes(
    router: APIRouter,
    resource: DataResource,
    agent_slug: str,
    server: Server,
) -> None:
    """Register all declared operation routes for one DataResource."""
    prefix = f"/data/{resource.name}"

    if resource.on_list is not None:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "list")
        router.add_api_route(
            f"{prefix}/",
            _make_list_handler(resource, prefix, agent_slug, server),
            methods=["GET"],
            # <-- REMOVED: Security(server.verify_api_key); api_router handles auth
            summary=f"List {resource.display_name_resolved}",
            operation_id=op_id,
            name=op_id,
        )

    if resource.on_get is not None:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "get")
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_get_handler(resource, prefix, agent_slug, server),
            methods=["GET"],
            # <-- REMOVED: Security(server.verify_api_key); api_router handles auth
            summary=f"Get {resource.display_name_resolved}",
            operation_id=op_id,
            name=op_id,
        )

    if resource.on_create is not None and not resource.read_only:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "create")
        router.add_api_route(
            f"{prefix}/",
            _make_create_handler(resource, prefix, agent_slug, server),
            methods=["POST"],
            dependencies=[
                Depends(require_scope("write"))
            ],  # <-- MODIFIED: scope-enforced write
            summary=f"Create {resource.display_name_resolved}",
            operation_id=op_id,
            name=op_id,
        )

    if resource.on_update is not None and not resource.read_only:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "update")
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_update_handler(resource, prefix, agent_slug, server),
            methods=["PUT"],
            dependencies=[
                Depends(require_scope("write"))
            ],  # <-- MODIFIED: scope-enforced write
            summary=f"Update {resource.display_name_resolved}",
            operation_id=op_id,
            name=op_id,
        )

    if resource.on_delete is not None and not resource.read_only:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "delete")
        router.add_api_route(
            f"{prefix}/{{item_id}}",
            _make_delete_handler(resource, prefix, agent_slug, server),
            methods=["DELETE"],
            dependencies=[
                Depends(require_scope("write"))
            ],  # <-- MODIFIED: scope-enforced write
            summary=f"Delete {resource.display_name_resolved}",
            operation_id=op_id,
            name=op_id,
        )

    if resource.importable and resource.on_import is not None:
        op_id = _data_resource_operation_id(agent_slug, resource.name, "import")
        router.add_api_route(
            f"{prefix}/import/",
            _make_import_handler(resource, prefix, agent_slug, server),
            methods=["POST"],
            dependencies=[
                Depends(require_scope("write"))
            ],  # <-- MODIFIED: scope-enforced write
            summary=f"Import {resource.display_name_resolved} (bulk)",
            operation_id=op_id,
            name=op_id,
        )


def _make_list_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    async def _handler(
        request: Request,
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        log.info(f"📥 GET {prefix}/ [DataResource list: {r.name}]")
        result = _call_with_context(
            r.on_list,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "list")
            ),
        )
        return result[skip : skip + limit]

    return _handler


def _make_get_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    async def _handler(request: Request, item_id: str) -> dict[str, Any]:
        log.info(f"📥 GET {prefix}/{item_id} [DataResource get: {r.name}]")
        result = _call_with_context(
            r.on_get,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "get")
            ),
            item_id,
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"{r.name} '{item_id}' not found"
            )
        return result

    return _handler


def _make_create_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    async def _handler(
        request: Request, data: dict[str, Any] = Body(...)
    ) -> JSONResponse:
        log.info(f"📥 POST {prefix}/ [DataResource create: {r.name}]")
        result = _call_with_context(
            r.on_create,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "create")
            ),
            data,
        )
        if not isinstance(result, dict) or "id" not in result:
            raise HTTPException(
                status_code=500,
                detail=f"on_create for '{r.name}' must return a dict with 'id'",
            )
        return JSONResponse(content=result, status_code=201)

    return _handler


def _make_update_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    on_update = r.on_update
    assert on_update is not None  # route registered only when on_update is set

    async def _handler(
        request: Request, item_id: str, data: dict[str, Any] = Body(...)
    ) -> dict[str, Any]:
        log.info(f"📥 PUT {prefix}/{item_id} [DataResource update: {r.name}]")
        result = _call_with_context(
            on_update,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "update")
            ),
            item_id,
            data,
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"{r.name} '{item_id}' not found"
            )
        return result

    return _handler


def _make_delete_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    async def _handler(request: Request, item_id: str) -> JSONResponse:
        log.info(f"📥 DELETE {prefix}/{item_id} [DataResource delete: {r.name}]")
        success = _call_with_context(
            r.on_delete,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "delete")
            ),
            item_id,
        )
        if not success:
            raise HTTPException(
                status_code=404, detail=f"{r.name} '{item_id}' not found"
            )
        return JSONResponse(content={"deleted": True}, status_code=200)

    return _handler


def _make_import_handler(
    r: DataResource, prefix: str, agent_slug: str, server: Server
) -> Any:
    async def _handler(
        request: Request, records: list[dict[str, Any]] = Body(...)
    ) -> dict[str, Any]:
        log.info(f"📥 POST {prefix}/import/ [DataResource import: {r.name}]")
        return _call_with_context(
            r.on_import,
            _context_from_request(
                request, agent_slug, server, _resource_scope(r, "import")
            ),
            records,
        )

    return _handler


def _context_from_request(
    request: Request, agent_slug: str, server: Server, required_scope: str
) -> DataResourceContext:
    raw_workspace = V2WorkspaceContext(
        id=request.headers.get("X-Supervaize-Workspace-Id") or "",
        slug=request.headers.get("X-Supervaize-Workspace-Slug"),
    )
    try:
        verified_workspace = verify_workspace_authorization_for_request(
            server=server,
            token=extract_workspace_authorization_token(request.headers),
            required_scopes=[required_scope],
            request_workspace=raw_workspace,
            agent_slug=agent_slug,
        )
    except WorkspaceAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    workspace_id: str | None
    workspace_slug: str | None
    if verified_workspace is not None:
        workspace_id = verified_workspace.workspace_id
        workspace_slug = verified_workspace.workspace_slug
    else:
        workspace_id = request.headers.get("X-Supervaize-Workspace-Id")
        workspace_slug = request.headers.get("X-Supervaize-Workspace-Slug")
    return DataResourceContext(
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        mission_id=request.headers.get("X-Supervaize-Mission-Id"),
        agent_slug=agent_slug,
        request_id=request.headers.get("X-Supervaize-Request-Id"),
        workspace_authorization=verified_workspace,
    )


def _resource_scope(resource: DataResource, operation: str) -> str:
    return f"resource.{resource.name}.{operation}"


def _accepts_context(callback: Any) -> bool:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return False
    return "context" in signature.parameters


def _call_with_context(
    callback: Any,
    context: DataResourceContext,
    *args: Any,
) -> Any:
    if callback is None:
        raise HTTPException(
            status_code=501, detail="DataResource callback not configured"
        )
    try:
        if _accepts_context(callback):
            return callback(*args, context=context)
        return callback(*args)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
