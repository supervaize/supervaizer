# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""FastAPI route generation for AnalyticsResource dashboard endpoints."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request

from supervaizer.analytics_resource import AnalyticsResource, AnalyticsResourceContext
from supervaizer.common import log

if TYPE_CHECKING:
    from supervaizer.agent import Agent
    from supervaizer.server import Server


def create_agent_analytics_routes(server: "Server", agent: "Agent") -> APIRouter:
    """Generate analytics REST routes for all AnalyticsResources on an agent."""
    router = APIRouter(prefix=agent.path, tags=["Analytics Resources"])
    agent_slug = agent.slug
    for resource in agent.analytics_resources:
        _add_resource_routes(router, resource, agent_slug)
    return router


def _analytics_resource_operation_id(
    agent_slug: str, resource_name: str, action: str
) -> str:
    """Build a globally unique OpenAPI operation_id."""
    return f"{agent_slug}_{resource_name}_analytics_{action}"


def _add_resource_routes(
    router: APIRouter,
    resource: AnalyticsResource,
    agent_slug: str,
) -> None:
    prefix = f"/analytics/{resource.name}"

    list_op_id = _analytics_resource_operation_id(
        agent_slug, resource.name, "list_dashboards"
    )
    router.add_api_route(
        f"{prefix}/dashboards/",
        _make_list_dashboards_handler(resource, prefix, agent_slug),
        methods=["GET"],
        summary=f"List {resource.display_name_resolved} dashboards",
        operation_id=list_op_id,
        name=list_op_id,
    )

    get_op_id = _analytics_resource_operation_id(
        agent_slug, resource.name, "get_dashboard"
    )
    router.add_api_route(
        f"{prefix}/dashboards/{{dashboard_id}}",
        _make_get_dashboard_handler(resource, prefix, agent_slug),
        methods=["GET"],
        summary=f"Get {resource.display_name_resolved} dashboard",
        operation_id=get_op_id,
        name=get_op_id,
    )

    dataset_op_id = _analytics_resource_operation_id(
        agent_slug, resource.name, "get_dataset"
    )
    router.add_api_route(
        f"{prefix}/dashboards/{{dashboard_id}}/datasets/{{dataset_id}}",
        _make_get_dataset_handler(resource, prefix, agent_slug),
        methods=["GET"],
        summary=f"Get {resource.display_name_resolved} dashboard dataset",
        operation_id=dataset_op_id,
        name=dataset_op_id,
    )


def _make_list_dashboards_handler(
    resource: AnalyticsResource,
    prefix: str,
    agent_slug: str,
) -> Any:
    async def _handler(request: Request) -> list[dict[str, Any]]:
        log.info(
            f"📈 GET {prefix}/dashboards/ [AnalyticsResource list: {resource.name}]"
        )
        if resource.on_list_dashboards is None:
            return resource.list_dashboards()
        return _call_with_context(
            resource.on_list_dashboards,
            _context_from_request(request, agent_slug),
        )

    return _handler


def _make_get_dashboard_handler(
    resource: AnalyticsResource,
    prefix: str,
    agent_slug: str,
) -> Any:
    async def _handler(request: Request, dashboard_id: str) -> dict[str, Any]:
        log.info(
            f"📈 GET {prefix}/dashboards/{dashboard_id} "
            f"[AnalyticsResource get: {resource.name}]"
        )
        if resource.on_get_dashboard is None:
            result = resource.get_static_dashboard(dashboard_id)
        else:
            result = _call_with_context(
                resource.on_get_dashboard,
                _context_from_request(request, agent_slug),
                dashboard_id,
            )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"{resource.name} dashboard '{dashboard_id}' not found",
            )
        return result

    return _handler


def _make_get_dataset_handler(
    resource: AnalyticsResource,
    prefix: str,
    agent_slug: str,
) -> Any:
    async def _handler(
        request: Request,
        dashboard_id: str,
        dataset_id: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        log.info(
            f"📈 GET {prefix}/dashboards/{dashboard_id}/datasets/{dataset_id} "
            f"[AnalyticsResource dataset: {resource.name}]"
        )
        result = _call_with_context(
            resource.on_get_dataset,
            _context_from_request(request, agent_slug),
            dashboard_id,
            dataset_id,
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"{resource.name} dataset '{dataset_id}' not found",
            )
        return result

    return _handler


def _context_from_request(
    request: Request, agent_slug: str
) -> AnalyticsResourceContext:
    return AnalyticsResourceContext(
        workspace_id=request.headers.get("X-Supervaize-Workspace-Id"),
        workspace_slug=request.headers.get("X-Supervaize-Workspace-Slug"),
        mission_id=request.headers.get("X-Supervaize-Mission-Id"),
        job_id=request.headers.get("X-Supervaize-Job-Id"),
        agent_slug=agent_slug,
        request_id=request.headers.get("X-Supervaize-Request-Id"),
        filters=_filters_from_request(request),
    )


def _filters_from_request(request: Request) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in request.query_params.multi_items():
        if key in filters:
            filters[key] = _append_filter_value(filters[key], value)
            continue
        filters[key] = value
    return filters


def _append_filter_value(existing: Any, value: str) -> list[Any]:
    if isinstance(existing, list):
        return [*existing, value]
    return [existing, value]


def _accepts_context(callback: Any) -> bool:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return False
    return "context" in signature.parameters


def _call_with_context(
    callback: Any,
    context: AnalyticsResourceContext,
    *args: Any,
) -> Any:
    if callback is None:
        raise HTTPException(
            status_code=501, detail="AnalyticsResource callback not configured"
        )
    try:
        if _accepts_context(callback):
            return callback(*args, context=context)
        return callback(*args)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
