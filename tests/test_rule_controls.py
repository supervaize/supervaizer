# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from supervaizer import Case
from supervaizer.contracts import (
    JobStartRequest,
    RuleCheckpointResponse,
    RuleCheckpointResume,
    RuleCheckpointSnapshot,
    V2ActionRequest,
    V2AgentCapabilities,
)
from supervaizer.lifecycle import EntityStatus
from supervaizer.rule_controls import (
    RuleCheckpointBlocked,
    RuleCheckpointGate,
    RuleCheckpointRecoveryRequired,
    _checkpoint_input_hash,
    _retain_decision,
    recover_guarded_step,
    run_guarded_step,
    resume_rule_checkpoint,
)
from supervaizer.server import _rule_checkpoint_resume_handler


def _response(status: str, snapshot_hash: str = "snapshot-1") -> Any:
    response = SimpleNamespace()
    response.raise_for_status = lambda: None
    response.json = lambda: {
        "checkpoint_id": f"checkpoint-{status}",
        "status": status,
        "snapshot_hash": snapshot_hash,
        "input_hash": "input-1",
    }
    return response


def test_rule_checkpoints_are_explicit_capability() -> None:
    undeclared = V2AgentCapabilities()
    assert undeclared.rule_checkpoints is None
    assert "rule_checkpoints" not in undeclared.model_dump(mode="json")
    capability = V2AgentCapabilities(
        rule_checkpoints={
            "phases": ["before", "after"],
            "secret_refs": ["case.metadata.customer_secret"],
        }
    )
    assert capability.rule_checkpoints is not None
    assert capability.rule_checkpoints.model_dump() == {
        "version": 1,
        "phases": ["before", "after"],
        "secret_refs": ["case.metadata.customer_secret"],
    }
    assert [action.id for action in capability.actions] == ["rule.checkpoint.resume"]


def test_governed_job_requires_rule_snapshot(account_fixture: Any) -> None:
    request = JobStartRequest(job_context={})
    assert "rule_snapshot" not in request.model_dump(mode="json")

    with pytest.raises(ValueError, match="requires rule_snapshot"):
        RuleCheckpointGate.from_job_start(account_fixture, request)


def test_gate_from_job_start_keeps_declared_secret_refs(account_fixture: Any) -> None:
    request = JobStartRequest(
        job_context={},
        rule_snapshot=RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="opaque-token",
        ),
    )

    gate = RuleCheckpointGate.from_job_start(
        account_fixture,
        request,
        secret_refs=("case.metadata.customer_secret",),
    )

    assert gate.secret_refs == ["case.metadata.customer_secret"]


def test_gate_from_v2_action_request_reads_rule_snapshot(account_fixture: Any) -> None:
    request = V2ActionRequest(
        request_id="request-1",
        actor={"user_id": "studio"},
        workspace={"id": "workspace-1"},
        mission_id="mission-1",
        agent_slug="agent-1",
        surface="job.start",
        action="job.start",
        job_id="job-1",
        input={
            "rule_snapshot": {
                "hash": "snapshot-1",
                "checkpoint_url": "https://studio.example/api/v1/rule-checkpoints/",
                "version": 1,
                "checkpoint_token": "opaque-token",
            }
        },
    )

    gate = RuleCheckpointGate.from_job_start(account_fixture, request)

    assert gate.snapshot.hash == "snapshot-1"


@pytest.mark.asyncio
async def test_guarded_step_prevents_effect_before_allow(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    post = mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(return_value=_response("stop")),
    )
    effect = mocker.AsyncMock(return_value="effect-result")
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
        secret_refs=("case.metadata.customer_secret",),
    )

    with pytest.raises(RuleCheckpointBlocked, match="stop"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={"state": "proposed"},
            effect=effect,
            after_context=lambda result: {"state": result},
        )

    effect.assert_not_awaited()
    assert post.await_count == 1
    assert post.await_args.kwargs["headers"]["X-Rule-Checkpoint-Token"] == "token"
    assert post.await_args.kwargs["json"]["secret_refs"] == [
        "case.metadata.customer_secret"
    ]


@pytest.mark.asyncio
async def test_guarded_step_prevents_advancement_after_stop(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    post = mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(side_effect=[_response("allow"), _response("stop")]),
    )
    effect = mocker.AsyncMock(return_value="effect-result")
    advance = mocker.AsyncMock()
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuleCheckpointBlocked, match="stop"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={"state": "proposed"},
            effect=effect,
            after_context=lambda result: {"state": result},
            advance=advance,
        )

    effect.assert_awaited_once()
    advance.assert_not_awaited()
    assert post.await_args_list[1].kwargs["json"]["occurrence_id"] == "occurrence-1"


@pytest.mark.asyncio
async def test_checkpoint_rejects_snapshot_mismatch(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(return_value=_response("allow", "different-snapshot")),
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuntimeError, match="snapshot_hash"):
        await gate.checkpoint(
            occurrence_id="occurrence-1",
            phase="before",
            job_id="job-1",
            case_id="case-1",
            step_id="step-1",
            context={},
        )


@pytest.mark.asyncio
async def test_checkpoint_failure_does_not_run_effect(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(side_effect=httpx.ConnectError("offline")),
    )
    effect = mocker.AsyncMock()
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuntimeError, match="Rule checkpoint request failed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )

    effect.assert_not_awaited()


@pytest.mark.asyncio
async def test_before_checkpoint_failure_retries_same_context_without_effect(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(
            side_effect=[httpx.ConnectError("offline"), _response("stop")]
        ),
    )
    effect = mocker.AsyncMock()
    case = SimpleNamespace(
        id="case-retry",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuntimeError, match="Rule checkpoint request failed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-retry",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda _: {},
        )
    with pytest.raises(RuleCheckpointBlocked, match="stop"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-retry",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda _: {},
        )
    effect.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkpoint_resume_resolves_matching_pending_decision(
    account_fixture: Any,
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    response = RuleCheckpointResponse(
        checkpoint_id="checkpoint-1",
        status="pause",
        snapshot_hash="snapshot-1",
        input_hash="input-1",
    )
    waiting = asyncio.create_task(
        gate.wait_for_resume(
            response, "occurrence-1", "before", job_id="job-1", case_id="case-1"
        )
    )
    await asyncio.sleep(0)

    gate.resume(
        RuleCheckpointResume(
            checkpoint_id="checkpoint-1",
            job_id="job-1",
            case_id="case-1",
            occurrence_id="occurrence-1",
            phase="before",
            status="allow",
            snapshot_hash="snapshot-1",
            input_hash="input-1",
            decision_id="decision-1",
        )
    )

    assert (await waiting).status == "allow"


@pytest.mark.asyncio
async def test_checkpoint_credentials_go_only_to_configured_studio(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    post = mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(return_value=_response("allow")),
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://attacker.example/collect",
            version=1,
            checkpoint_token="token",
        ),
    )

    await gate.checkpoint(
        occurrence_id="occurrence-1",
        phase="before",
        job_id="job-1",
        case_id="case-1",
        step_id="step-1",
        context={},
    )

    assert post.await_args.args[0] == (
        f"{account_fixture.api_url}/api/v1/rule-checkpoints/"
    )


@pytest.mark.asyncio
async def test_pause_resume_is_rejected_and_keeps_waiter_pending(
    account_fixture: Any,
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    waiting = asyncio.create_task(
        gate.wait_for_resume(
            RuleCheckpointResponse(
                checkpoint_id="checkpoint-pause",
                status="pause",
                snapshot_hash="snapshot-1",
                input_hash="input-1",
            ),
            "occurrence-1",
            "before",
            job_id="job-1",
            case_id="case-1",
        )
    )
    await asyncio.sleep(0)
    decision = {
        "checkpoint_id": "checkpoint-pause",
        "job_id": "job-1",
        "case_id": "case-1",
        "occurrence_id": "occurrence-1",
        "phase": "before",
        "snapshot_hash": "snapshot-1",
        "input_hash": "input-1",
        "decision_id": "decision-1",
    }

    with pytest.raises(ValidationError):
        RuleCheckpointResume.model_validate(decision | {"status": "pause"})
    assert not waiting.done()

    gate.resume(RuleCheckpointResume.model_validate(decision | {"status": "allow"}))
    assert (await waiting).status == "allow"


def _resume(checkpoint_id: str, case_id: str = "case-1") -> RuleCheckpointResume:
    return RuleCheckpointResume(
        checkpoint_id=checkpoint_id,
        job_id="job-1",
        case_id=case_id,
        occurrence_id="occurrence-1",
        phase="before",
        status="allow",
        snapshot_hash="snapshot-1",
        input_hash="input-1",
        decision_id="decision-1",
    )


def _paused(checkpoint_id: str) -> RuleCheckpointResponse:
    return RuleCheckpointResponse(
        checkpoint_id=checkpoint_id,
        status="pause",
        snapshot_hash="snapshot-1",
        input_hash="input-1",
    )


def _gate(account: Any) -> RuleCheckpointGate:
    return RuleCheckpointGate(
        account,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )


@pytest.mark.asyncio
async def test_live_resume_for_another_case_does_not_release_gate(
    account_fixture: Any,
) -> None:
    gate = _gate(account_fixture)
    waiting = asyncio.create_task(
        gate.wait_for_resume(
            _paused("checkpoint-bound"),
            "occurrence-1",
            "before",
            job_id="job-1",
            case_id="case-1",
        )
    )
    await asyncio.sleep(0)

    with pytest.raises(ValueError, match="does not match pending occurrence"):
        resume_rule_checkpoint(_resume("checkpoint-bound", case_id="case-other"))
    assert not waiting.done()

    resume_rule_checkpoint(_resume("checkpoint-bound"))
    assert (await waiting).status == "allow"


@pytest.mark.asyncio
async def test_mismatched_early_decision_is_discarded(account_fixture: Any) -> None:
    assert resume_rule_checkpoint(_resume("checkpoint-early", "case-other")) is None
    gate = _gate(account_fixture)
    waiting = asyncio.create_task(
        gate.wait_for_resume(
            _paused("checkpoint-early"),
            "occurrence-1",
            "before",
            job_id="job-1",
            case_id="case-1",
        )
    )
    await asyncio.sleep(0)
    assert not waiting.done()

    resume_rule_checkpoint(_resume("checkpoint-early"))
    assert (await waiting).status == "allow"


def test_retained_decisions_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    retained: dict[str, RuleCheckpointResume] = {}
    monkeypatch.setattr("supervaizer.rule_controls._DELIVERED_DECISIONS", retained)
    monkeypatch.setattr("supervaizer.rule_controls._DELIVERED_DECISIONS_LIMIT", 2)

    for checkpoint_id in ("checkpoint-a", "checkpoint-b", "checkpoint-c"):
        _retain_decision(_resume(checkpoint_id))

    assert list(retained) == ["checkpoint-b", "checkpoint-c"]


@pytest.mark.asyncio
async def test_a2a_resume_handler_delivers_studio_payload(account_fixture: Any) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    waiting = asyncio.create_task(
        gate.wait_for_resume(
            RuleCheckpointResponse(
                checkpoint_id="checkpoint-a2a",
                status="pause",
                snapshot_hash="snapshot-1",
                input_hash="input-1",
            ),
            "occurrence-1",
            "before",
            job_id="job-1",
            case_id="case-1",
        )
    )
    await asyncio.sleep(0)
    result = _rule_checkpoint_resume_handler(
        V2ActionRequest(
            request_id="request-1",
            actor={"user_id": "studio"},
            workspace={"id": "workspace-1"},
            mission_id="mission-1",
            agent_slug="agent-1",
            surface="mission.agent",
            action="rule.checkpoint.resume",
            job_id="job-1",
            case_id="case-1",
            input={
                "checkpoint_id": "checkpoint-a2a",
                "occurrence_id": "occurrence-1",
                "phase": "before",
                "status": "allow",
                "snapshot_hash": "snapshot-1",
                "input_hash": "input-1",
                "decision_id": "decision-1",
            },
        )
    )

    assert result.effects[0].status == "allow"
    assert (await waiting).status == "allow"


@pytest.mark.asyncio
async def test_checkpoint_resume_retained_until_waiter_is_registered(
    account_fixture: Any,
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    decision = RuleCheckpointResume(
        checkpoint_id="checkpoint-race",
        job_id="job-1",
        case_id="case-1",
        occurrence_id="occurrence-1",
        phase="before",
        status="allow",
        snapshot_hash="snapshot-1",
        input_hash="input-1",
        decision_id="decision-1",
    )
    assert resume_rule_checkpoint(decision) is None

    resumed = await gate.wait_for_resume(
        RuleCheckpointResponse(
            checkpoint_id="checkpoint-race",
            status="pause",
            snapshot_hash="snapshot-1",
            input_hash="input-1",
        ),
        "occurrence-1",
        "before",
        job_id="job-1",
        case_id="case-1",
    )
    assert resumed.status == "allow"


@pytest.mark.asyncio
async def test_persisted_resume_wakes_later_waiter(
    account_fixture: Any, storage_manager: Any
) -> None:
    state = {
        "checkpoint_id": "checkpoint-race",
        "occurrence_id": "occurrence-1",
        "phase": "before",
        "snapshot_hash": "snapshot-1",
        "input_hash": "input-1",
        "status": "pause",
    }
    case = Case(
        id="case-race",
        job_id="job-1",
        account=account_fixture,
        name="Persisted rule case",
        description="Resume checkpoint delivery",
        status=EntityStatus.IN_PROGRESS,
        metadata={"_rule_checkpoints": {"occurrence-1:before": state}},
    )
    decision = RuleCheckpointResume(
        checkpoint_id="checkpoint-race",
        job_id="job-1",
        case_id="case-race",
        occurrence_id="occurrence-1",
        phase="before",
        status="allow",
        snapshot_hash="snapshot-1",
        input_hash="input-1",
        decision_id="decision-1",
    )

    assert resume_rule_checkpoint(decision) is not None
    assert state["status"] == "allow"
    assert (
        storage_manager.get_object_by_id("Case", case.id)["metadata"][
            "_rule_checkpoints"
        ]["occurrence-1:before"]["status"]
        == "allow"
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    resumed = await gate.wait_for_resume(
        RuleCheckpointResponse(
            checkpoint_id="checkpoint-race",
            status="pause",
            snapshot_hash="snapshot-1",
            input_hash="input-1",
        ),
        "occurrence-1",
        "before",
        job_id="job-1",
        case_id="case-race",
    )

    assert resumed.status == "allow"


@pytest.mark.asyncio
async def test_started_effect_is_never_replayed_after_failure(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(return_value=_response("allow")),
    )
    effect = mocker.AsyncMock(side_effect=RuntimeError("effect failed"))
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuntimeError, match="effect failed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )
    with pytest.raises(RuleCheckpointRecoveryRequired, match="claimed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )
    effect.assert_awaited_once()


@pytest.mark.asyncio
async def test_lost_after_response_never_replays_completed_effect(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(
            side_effect=[_response("allow"), httpx.ConnectError("offline")]
        ),
    )
    effect = mocker.AsyncMock(return_value="done")
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )

    with pytest.raises(RuntimeError, match="Rule checkpoint request failed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )
    with pytest.raises(RuleCheckpointRecoveryRequired, match="claimed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )
    effect.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_retries_pending_after_without_replaying_effect(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    checkpoint = mocker.patch.object(
        gate,
        "checkpoint",
        side_effect=[
            RuleCheckpointResponse(
                checkpoint_id="before-checkpoint",
                status="allow",
                snapshot_hash="snapshot-1",
                input_hash="before-input",
            ),
            RuntimeError("transport lost"),
            RuleCheckpointResponse(
                checkpoint_id="after-checkpoint",
                status="allow",
                snapshot_hash="snapshot-1",
                input_hash="after-input",
            ),
        ],
    )
    effect = mocker.AsyncMock(return_value="done")
    advance = mocker.AsyncMock()
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )

    with pytest.raises(RuntimeError, match="transport lost"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda result: {"result": result},
            advance=advance,
        )
    with pytest.raises(ValueError, match="context changed"):
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            after_context=lambda result: {"result": f"other-{result}"},
            advance=advance,
        )

    assert (
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            after_context=lambda result: {"result": result},
            advance=advance,
        )
        == "done"
    )
    effect.assert_awaited_once()
    advance.assert_awaited_once_with("done")
    assert checkpoint.await_count == 3
    assert checkpoint.await_args.kwargs["occurrence_id"] == "occurrence-1"
    assert checkpoint.await_args.kwargs["phase"] == "after"


@pytest.mark.asyncio
async def test_persisted_before_allow_continues_without_rechecking(
    account_fixture: Any, mocker: MockerFixture, storage_manager: Any
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    checkpoint = mocker.patch.object(
        gate,
        "checkpoint",
        return_value=RuleCheckpointResponse(
            checkpoint_id="after-checkpoint",
            status="allow",
            snapshot_hash="snapshot-1",
            input_hash="after-input",
        ),
    )
    effect = mocker.AsyncMock(return_value="done")
    case = Case(
        id="case-before-allow",
        job_id="job-before-allow",
        account=account_fixture,
        name="Persisted before allow",
        description="Restart continuation",
        status=EntityStatus.IN_PROGRESS,
        metadata={
            "_rule_checkpoint_case_registered": True,
            "_rule_checkpoints": {
                "occurrence-1:before": {
                    "occurrence_id": "occurrence-1",
                    "phase": "before",
                    "snapshot_hash": "snapshot-1",
                    "step_id": "step-1",
                    "context_hash": _checkpoint_input_hash({"proposed": True}),
                    "status": "allow",
                }
            },
        },
    )
    persisted = storage_manager.get_object_by_id("Case", case.id)
    assert persisted is not None
    restarted_case = SimpleNamespace(
        id=case.id,
        job_id=case.job_id,
        metadata=persisted["metadata"],
        _persist=mocker.Mock(),
    )
    assert (
        await run_guarded_step(
            gate=gate,
            case=restarted_case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda result: {"result": result},
        )
        == "done"
    )
    effect.assert_awaited_once()
    assert checkpoint.await_count == 1


@pytest.mark.asyncio
async def test_persisted_before_allow_rejects_changed_step(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    checkpoint = mocker.AsyncMock()
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    mocker.patch.object(gate, "checkpoint", checkpoint)
    effect = mocker.AsyncMock()
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={
            "_rule_checkpoint_case_registered": True,
            "_rule_checkpoints": {
                "occurrence-1:before": {
                    "occurrence_id": "occurrence-1",
                    "phase": "before",
                    "snapshot_hash": "snapshot-1",
                    "step_id": "step-1",
                    "context_hash": _checkpoint_input_hash({"proposed": True}),
                    "status": "allow",
                }
            },
        },
        _persist=lambda: None,
    )

    with pytest.raises(ValueError, match="step changed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="different-step",
            occurrence_id="occurrence-1",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda result: {"result": result},
        )

    effect.assert_not_awaited()
    checkpoint.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_recovery_advances_only_once(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    mocker.patch.object(
        gate,
        "checkpoint",
        return_value=RuleCheckpointResponse(
            checkpoint_id="after-checkpoint",
            status="allow",
            snapshot_hash="snapshot-1",
            input_hash="after-input",
        ),
    )
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={
            "_rule_checkpoints": {
                "occurrence-1:after": {
                    "occurrence_id": "occurrence-1",
                    "phase": "after",
                    "snapshot_hash": "snapshot-1",
                    "step_id": "step-1",
                    "context_hash": _checkpoint_input_hash({"result": "done"}),
                    "effect_started": True,
                    "effect_completed": True,
                    "status": "pending",
                }
            }
        },
        _persist=lambda: None,
    )
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def advance(_: str) -> None:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    recovery = asyncio.create_task(
        recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            after_context=lambda result: {"result": result},
            advance=advance,
        )
    )
    await started.wait()
    with pytest.raises(RuleCheckpointRecoveryRequired, match="active"):
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            after_context=lambda result: {"result": result},
            advance=advance,
        )
    release.set()
    assert await recovery == "done"
    assert (
        await recover_guarded_step(
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            advance=advance,
        )
        == "done"
    )
    assert calls == 1


@pytest.mark.asyncio
async def test_recovery_cannot_advance_while_original_after_request_is_active(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    after_waiting = asyncio.Event()
    release_after = asyncio.Event()
    calls: list[str] = []

    async def checkpoint(**kwargs: Any) -> RuleCheckpointResponse:
        if kwargs["phase"] == "before":
            return RuleCheckpointResponse(
                checkpoint_id="before-checkpoint",
                status="allow",
                snapshot_hash="snapshot-1",
                input_hash="before-input",
            )
        after_waiting.set()
        await release_after.wait()
        return RuleCheckpointResponse(
            checkpoint_id="after-checkpoint",
            status="allow",
            snapshot_hash="snapshot-1",
            input_hash="after-input",
        )

    mocker.patch.object(gate, "checkpoint", side_effect=checkpoint)
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )

    async def effect() -> str:
        calls.append("effect")
        return "done"

    async def advance(_: str) -> None:
        calls.append("advance")

    original = asyncio.create_task(
        run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={"proposed": True},
            effect=effect,
            after_context=lambda result: {"result": result},
            advance=advance,
        )
    )
    await after_waiting.wait()

    with pytest.raises(RuleCheckpointRecoveryRequired, match="active"):
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-1",
            result="done",
            after_context=lambda result: {"result": result},
            advance=advance,
        )

    release_after.set()
    assert await original == "done"
    assert calls == ["effect", "advance"]


@pytest.mark.asyncio
async def test_duplicate_completed_occurrence_never_replays_effect(
    account_fixture: Any, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.rule_controls._httpx_client.post",
        new=mocker.AsyncMock(side_effect=[_response("allow"), _response("allow")]),
    )
    effect = mocker.AsyncMock(return_value="done")
    case = SimpleNamespace(
        id="case-1",
        job_id="job-1",
        metadata={"_rule_checkpoint_case_registered": True},
        _persist=lambda: None,
    )
    gate = RuleCheckpointGate(
        account_fixture,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="token",
        ),
    )
    await run_guarded_step(
        gate=gate,
        case=case,
        step_id="step-1",
        occurrence_id="occurrence-1",
        before_context={},
        effect=effect,
        after_context=lambda _: {},
    )
    with pytest.raises(RuleCheckpointRecoveryRequired, match="claimed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="step-1",
            occurrence_id="occurrence-1",
            before_context={},
            effect=effect,
            after_context=lambda _: {},
        )
    effect.assert_awaited_once()
