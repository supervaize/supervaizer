# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""A2A JSON-RPC controller methods for Supervaizer v2."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, ValidationError

from supervaizer.contracts import ContractModel, V2ActionRequest, V2ActionResult

if TYPE_CHECKING:
    from supervaizer.server import Server

SUPERVAIZER_ACTION_INVOKE_METHOD = "supervaizer/action.invoke"

JSON_RPC_METHOD_NOT_FOUND = -32601
JSON_RPC_INVALID_PARAMS = -32602
JSON_RPC_ACTION_NOT_REGISTERED = -32010
JSON_RPC_INTERNAL_ERROR = -32603

ActionHandler = Callable[
    [V2ActionRequest],
    V2ActionResult | dict[str, Any] | Awaitable[V2ActionResult | dict[str, Any]],
]
ActionHandlerKey = tuple[str, str]


class JsonRpcRequest(ContractModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcError(ContractModel):
    code: int
    message: str
    data: dict[str, Any] | None = None


class JsonRpcResponse(ContractModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: JsonRpcError | None = None


def register_v2_action_handler(
    server: "Server",
    action: str,
    handler: ActionHandler,
    *,
    agent_slug: str | None = None,
) -> None:
    """Register a Supervaizer v2 action handler for the current server process."""
    handlers = _get_action_handlers(server)
    handlers[_action_handler_key(_resolve_agent_slug(server, agent_slug), action)] = (
        handler
    )


async def dispatch_json_rpc(server: "Server", body: dict[str, Any]) -> JsonRpcResponse:
    """Dispatch one A2A JSON-RPC request."""
    try:
        request = JsonRpcRequest.model_validate(body)
    except ValidationError as exc:
        return _json_rpc_error(
            request_id=body.get("id"),
            code=JSON_RPC_INVALID_PARAMS,
            message="Invalid JSON-RPC request",
            data={"errors": exc.errors()},
        )

    if request.method != SUPERVAIZER_ACTION_INVOKE_METHOD:
        return _json_rpc_error(
            request_id=request.id,
            code=JSON_RPC_METHOD_NOT_FOUND,
            message=f"Method not found: {request.method}",
        )

    return await _dispatch_action(server, request)


async def _dispatch_action(
    server: "Server", request: JsonRpcRequest
) -> JsonRpcResponse:
    try:
        action_request = _validate_action_request(request.params)
    except ValidationError as exc:
        return _json_rpc_error(
            request_id=request.id,
            code=JSON_RPC_INVALID_PARAMS,
            message="Invalid Supervaizer v2 action request",
            data={"errors": exc.errors()},
        )

    handler = _get_action_handlers(server).get(
        _action_handler_key(action_request.agent_slug, action_request.action)
    )
    if handler is None:
        return _json_rpc_error(
            request_id=request.id,
            code=JSON_RPC_ACTION_NOT_REGISTERED,
            message=f"Action handler not registered: {action_request.action}",
            data={
                "agent_slug": action_request.agent_slug,
                "action": action_request.action,
            },
        )

    try:
        handler_result = handler(action_request)
        if isawaitable(handler_result):
            handler_result = await handler_result
        result = V2ActionResult.model_validate(handler_result)
    except Exception as exc:
        return _json_rpc_error(
            request_id=request.id,
            code=JSON_RPC_INTERNAL_ERROR,
            message="Action handler failed",
            data={"action": action_request.action, "error": str(exc)},
        )

    return JsonRpcResponse(id=request.id, result=result.model_dump(mode="json"))


def _validate_action_request(params: dict[str, Any]) -> V2ActionRequest:
    action_payload = params.get("action_request", params)
    return V2ActionRequest.model_validate(action_payload)


def _get_action_handlers(server: "Server") -> dict[ActionHandlerKey, ActionHandler]:
    state = server.app.state
    handlers = getattr(state, "supervaizer_v2_action_handlers", None)
    if handlers is None:
        handlers = {}
        state.supervaizer_v2_action_handlers = handlers
    return handlers


def _resolve_agent_slug(server: "Server", agent_slug: str | None) -> str:
    agent_slugs = {agent.slug for agent in server.agents}
    if agent_slug:
        if agent_slug not in agent_slugs:
            raise ValueError(f"Unknown agent_slug for v2 action handler: {agent_slug}")
        return agent_slug
    if len(agent_slugs) == 1:
        return next(iter(agent_slugs))
    raise ValueError("agent_slug is required for multi-agent v2 action handlers")


def _action_handler_key(agent_slug: str, action: str) -> ActionHandlerKey:
    return (agent_slug, action)


def _json_rpc_error(
    *,
    request_id: str | int | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JsonRpcResponse:
    return JsonRpcResponse(
        id=request_id,
        error=JsonRpcError(code=code, message=message, data=data),
    )
