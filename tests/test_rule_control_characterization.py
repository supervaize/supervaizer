# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize rule checkpoint gates around effects and recovery."""

from collections.abc import Iterator
from typing import Literal

import pytest
from pytest_mock import MockerFixture

from supervaizer import Account, Case, EntityStatus
from supervaizer.case import Cases
from supervaizer.contracts import RuleCheckpointResponse, RuleCheckpointSnapshot
from supervaizer.job import Jobs
from supervaizer.rule_controls import (
    RuleCheckpointBlocked,
    RuleCheckpointGate,
    RuleCheckpointRecoveryRequired,
    _checkpoint_input_hash,
    recover_guarded_step,
    run_guarded_step,
)
from supervaizer.storage import StorageManager


@pytest.fixture
def isolated_rule_case_state(storage_manager: StorageManager) -> Iterator[None]:
    """Keep real case registries and persistence isolated per test."""
    del storage_manager
    Cases().reset()
    Jobs().reset()
    yield
    Cases().reset()
    Jobs().reset()


def _gate(account: Account) -> RuleCheckpointGate:
    """Create a typed gate with a stable checkpoint snapshot."""
    return RuleCheckpointGate(
        account,
        RuleCheckpointSnapshot(
            hash="snapshot-1",
            checkpoint_url="https://studio.example/api/v1/rule-checkpoints/",
            version=1,
            checkpoint_token="checkpoint-token",
        ),
        agent_slug="rule-agent",
    )


def _case(account: Account, case_id: str) -> Case:
    """Create a real case ready for explicit rule checkpoints."""
    return Case(
        id=case_id,
        job_id="rule-job",
        account=account,
        status=EntityStatus.IN_PROGRESS,
        name="Rule case",
        description="Rule control characterization",
        metadata={"_rule_checkpoint_case_registered": True},
    )


def _checkpoint(
    status: Literal["allow", "pause", "stop"], checkpoint_id: str
) -> RuleCheckpointResponse:
    """Build a checkpoint provider response for the selected outcome."""
    return RuleCheckpointResponse(
        checkpoint_id=checkpoint_id,
        status=status,
        snapshot_hash="snapshot-1",
        input_hash="provider-hash",
    )


@pytest.mark.asyncio
async def test_guarded_step_waits_for_before_resume_then_records_after_and_advance(
    isolated_rule_case_state: None,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """A paused before checkpoint resumes before the effect and later advances."""
    del isolated_rule_case_state
    case = _case(account_fixture, "pause-before-case")
    gate = _gate(account_fixture)
    checkpoint = mocker.patch.object(
        gate,
        "checkpoint",
        new=mocker.AsyncMock(
            side_effect=[
                _checkpoint("pause", "before-1"),
                _checkpoint("allow", "after-1"),
            ]
        ),
    )
    wait_for_resume = mocker.patch.object(
        gate,
        "wait_for_resume",
        new=mocker.AsyncMock(return_value=_checkpoint("allow", "before-1")),
    )
    events: list[str] = []

    async def effect() -> str:
        events.append("effect")
        return "result"

    async def advance(result: str) -> None:
        events.append(f"advance:{result}")

    result = await run_guarded_step(
        gate=gate,
        case=case,
        step_id="send-message",
        occurrence_id="occurrence-1",
        before_context={"draft": "hello"},
        effect=effect,
        after_context=lambda value: {"sent": value},
        advance=advance,
    )

    before = case.metadata["_rule_checkpoints"]["occurrence-1:before"]
    after = case.metadata["_rule_checkpoints"]["occurrence-1:after"]
    assert result == "result"
    assert events == ["effect", "advance:result"]
    assert checkpoint.await_count == 2
    assert wait_for_resume.await_count == 1
    assert before["status"] == "allow"
    assert before["step_id"] == "send-message"
    assert after["status"] == "allow"
    assert after["effect_completed"] is True
    assert after["advancement_completed"] is True
    assert after["context_hash"] == _checkpoint_input_hash({"sent": "result"})


@pytest.mark.asyncio
async def test_guarded_step_blocks_after_effect_without_advancing(
    isolated_rule_case_state: None,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """A stopped after checkpoint preserves completion but prevents advancement."""
    del isolated_rule_case_state
    case = _case(account_fixture, "stop-after-case")
    gate = _gate(account_fixture)
    mocker.patch.object(
        gate,
        "checkpoint",
        new=mocker.AsyncMock(
            side_effect=[
                _checkpoint("allow", "before-2"),
                _checkpoint("stop", "after-2"),
            ]
        ),
    )
    advanced: list[str] = []

    async def effect() -> str:
        return "effect-result"

    async def advance(result: str) -> None:
        advanced.append(result)

    with pytest.raises(RuleCheckpointBlocked, match="stop"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="send-message",
            occurrence_id="occurrence-2",
            before_context={"draft": "hello"},
            effect=effect,
            after_context=lambda value: {"sent": value},
            advance=advance,
        )

    after = case.metadata["_rule_checkpoints"]["occurrence-2:after"]
    assert advanced == []
    assert after["status"] == "stop"
    assert after["effect_started"] is True
    assert after["effect_completed"] is True
    assert "advancement_started" not in after


@pytest.mark.asyncio
async def test_guarded_step_effect_error_requires_explicit_recovery(
    isolated_rule_case_state: None,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """An effect failure leaves a claimed occurrence that recovery rejects."""
    del isolated_rule_case_state
    case = _case(account_fixture, "effect-error-case")
    gate = _gate(account_fixture)
    mocker.patch.object(
        gate,
        "checkpoint",
        new=mocker.AsyncMock(return_value=_checkpoint("allow", "before-3")),
    )

    async def failing_effect() -> str:
        raise RuntimeError("effect failed")

    with pytest.raises(RuntimeError, match="effect failed"):
        await run_guarded_step(
            gate=gate,
            case=case,
            step_id="send-message",
            occurrence_id="occurrence-3",
            before_context={"draft": "hello"},
            effect=failing_effect,
            after_context=lambda value: {"sent": value},
        )

    with pytest.raises(RuleCheckpointRecoveryRequired, match="not ready"):
        await recover_guarded_step(
            case=case,
            occurrence_id="occurrence-3",
            result="unreachable",
        )

    after = case.metadata["_rule_checkpoints"]["occurrence-3:after"]
    assert after["status"] == "pending"
    assert after["effect_started"] is True
    assert "effect_completed" not in after


@pytest.mark.asyncio
async def test_recovery_rechecks_pending_after_then_advances_once(
    isolated_rule_case_state: None,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """Recovery rechecks a completed effect and records one advancement."""
    del isolated_rule_case_state
    case = _case(account_fixture, "recovery-case")
    gate = _gate(account_fixture)
    context = {"sent": "result"}
    case.metadata["_rule_checkpoints"] = {
        "occurrence-4:after": {
            "occurrence_id": "occurrence-4",
            "phase": "after",
            "snapshot_hash": "snapshot-1",
            "step_id": "send-message",
            "status": "pending",
            "effect_started": True,
            "effect_completed": True,
            "context_hash": _checkpoint_input_hash(context),
        }
    }
    checkpoint = mocker.patch.object(
        gate,
        "checkpoint",
        new=mocker.AsyncMock(return_value=_checkpoint("allow", "after-4")),
    )
    advanced: list[str] = []

    async def advance(result: str) -> None:
        advanced.append(result)

    result = await recover_guarded_step(
        gate=gate,
        case=case,
        occurrence_id="occurrence-4",
        result="result",
        after_context=lambda value: {"sent": value},
        advance=advance,
    )
    repeated = await recover_guarded_step(
        case=case,
        occurrence_id="occurrence-4",
        result="result",
        advance=advance,
    )

    after = case.metadata["_rule_checkpoints"]["occurrence-4:after"]
    assert result == repeated == "result"
    assert checkpoint.await_count == 1
    assert advanced == ["result"]
    assert after["status"] == "allow"
    assert after["advancement_started"] is True
    assert after["advancement_completed"] is True


@pytest.mark.asyncio
async def test_recovery_rejects_changed_snapshot_or_after_context(
    isolated_rule_case_state: None,
    account_fixture: Account,
) -> None:
    """Pending recovery rejects a different snapshot or reconstructed context."""
    del isolated_rule_case_state
    case = _case(account_fixture, "recovery-validation-case")
    gate = _gate(account_fixture)
    case.metadata["_rule_checkpoints"] = {
        "occurrence-5:after": {
            "occurrence_id": "occurrence-5",
            "phase": "after",
            "snapshot_hash": "other-snapshot",
            "step_id": "send-message",
            "status": "pending",
            "effect_started": True,
            "effect_completed": True,
            "context_hash": _checkpoint_input_hash({"sent": "stored"}),
        }
    }

    with pytest.raises(ValueError, match="snapshot changed"):
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-5",
            result="result",
            after_context=lambda value: {"sent": value},
        )

    case.metadata["_rule_checkpoints"]["occurrence-5:after"]["snapshot_hash"] = (
        "snapshot-1"
    )
    with pytest.raises(ValueError, match="context changed"):
        await recover_guarded_step(
            gate=gate,
            case=case,
            occurrence_id="occurrence-5",
            result="result",
            after_context=lambda value: {"sent": value},
        )
