# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""The confirm idempotency conformance helper agents run in their own tests."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from supervaizer import assert_confirm_idempotent
from supervaizer.contracts import V2ActionRequest


def _request() -> V2ActionRequest:
    return V2ActionRequest(
        request_id="request-1",
        actor={"user_id": "user-1"},
        workspace={"id": "workspace-1", "slug": "workspace"},
        mission_id="mission-1",
        agent_slug="agent-1",
        surface="job.start",
        action="job.start",
        idempotency_key="idem-1",
        job_id="job-1",
    )


def test_assert_confirm_idempotent_accepts_a_replayed_result() -> None:
    created: dict[str, dict[str, Any]] = {}

    def handler(request: V2ActionRequest) -> dict[str, Any]:
        key = request.idempotency_key or ""
        if key not in created:
            created[key] = {
                "status": "ok",
                "effects": [{"type": "job.started", "job_id": request.job_id}],
                "replay_safety": {"strictly_idempotent_response": True},
            }
        return created[key]

    result = assert_confirm_idempotent(handler, _request())

    assert result.effects[0].job_id == "job-1"
    assert len(created) == 1


def test_assert_confirm_idempotent_rejects_a_second_effect() -> None:
    calls = itertools.count(1)

    def handler(request: V2ActionRequest) -> dict[str, Any]:
        return {
            "status": "ok",
            "effects": [{"type": "job.started", "job_id": f"job-{next(calls)}"}],
        }

    with pytest.raises(
        AssertionError, match="reported new effects: \\['job.started'\\]"
    ):
        assert_confirm_idempotent(handler, _request())


def test_assert_confirm_idempotent_rejects_a_different_result() -> None:
    statuses = iter(["ok", "error"])

    def handler(request: V2ActionRequest) -> dict[str, Any]:
        return {"status": next(statuses)}

    with pytest.raises(AssertionError, match="returned a different result"):
        assert_confirm_idempotent(handler, _request())


def test_assert_confirm_idempotent_awaits_async_handlers() -> None:
    async def handler(request: V2ActionRequest) -> dict[str, Any]:
        return {"status": "ok", "effects": [{"type": "job.started", "job_id": "job-1"}]}

    assert assert_confirm_idempotent(handler, _request()).status == "ok"
