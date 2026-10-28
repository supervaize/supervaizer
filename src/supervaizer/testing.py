# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Conformance helpers agents import into their own test suites."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from typing import Any

from supervaizer.contracts import V2ActionRequest, V2ActionResult


async def _await(value: Awaitable[Any]) -> Any:
    return await value


def _call(handler: Callable[[V2ActionRequest], Any], request: V2ActionRequest) -> Any:
    # ponytail: sync entry point; call it from a sync test, not inside a loop.
    result = handler(request)
    if isawaitable(result):
        result = asyncio.run(_await(result))
    return V2ActionResult.model_validate(result)


def assert_confirm_idempotent(
    handler: Callable[[V2ActionRequest], Any], request: V2ActionRequest
) -> V2ActionResult:
    """Call ``handler`` twice with the same request; the replay must change nothing.

    Raises ``AssertionError`` when the second call reports an effect the first
    call did not, or returns a different result. Returns the first result.
    """
    first = _call(handler, request)
    second = _call(handler, request)
    new_effects = [effect for effect in second.effects if effect not in first.effects]
    if new_effects:
        raise AssertionError(
            f"replay of {request.action!r} with idempotency_key "
            f"{request.idempotency_key!r} reported new effects: "
            f"{[effect.type for effect in new_effects]}"
        )
    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    if first_payload != second_payload:
        raise AssertionError(
            f"replay of {request.action!r} with idempotency_key "
            f"{request.idempotency_key!r} returned a different result:\n"
            f"first:  {first_payload}\nsecond: {second_payload}"
        )
    return first
