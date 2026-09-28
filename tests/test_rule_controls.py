from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from supervaizer.contracts import (
    JobStartRequest,
    RuleCheckpointResponse,
    RuleCheckpointResume,
    RuleCheckpointSnapshot,
    V2ActionRequest,
    V2AgentCapabilities,
)
from supervaizer.rule_controls import (
    RuleCheckpointBlocked,
    RuleCheckpointGate,
    RuleCheckpointRecoveryRequired,
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
        gate.wait_for_resume(response, "occurrence-1", "before")
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
