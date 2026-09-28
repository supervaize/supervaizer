"""Explicit SDK helpers for Studio rule checkpoint gates.

Agents must put cooperative effects inside ``run_guarded_step`` and declare
business-secret paths in ``secret_refs``. An after gate cannot undo a completed
external effect, and ambiguous recovery never replays one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import asyncio
import hashlib
import httpx
import json

from supervaizer.account_service import _httpx_client
from supervaizer.contracts import (
    JobStartRequest,
    RuleCheckpointRequest,
    RuleCheckpointResponse,
    RuleCheckpointResume,
    RuleCheckpointSnapshot,
    V2ActionRequest,
)

if TYPE_CHECKING:
    from supervaizer.account import Account
    from supervaizer.case import Case

T = TypeVar("T")
_PENDING_GATES: dict[str, "RuleCheckpointGate"] = {}
_DELIVERED_DECISIONS: dict[str, RuleCheckpointResume] = {}
_ACTIVE_OCCURRENCES: set[tuple[str, str]] = set()


class RuleCheckpointBlocked(RuntimeError):
    """Studio did not authorize the checkpoint occurrence."""

    def __init__(self, response: RuleCheckpointResponse) -> None:
        self.response = response
        super().__init__(
            f"Rule checkpoint {response.checkpoint_id!r} returned {response.status!r}"
        )


class RuleCheckpointRecoveryRequired(RuntimeError):
    """A restart must resume a completed effect without replaying it."""


class RuleCheckpointGate:
    """Posts explicit, idempotent rule checkpoints with controller credentials."""

    def __init__(
        self,
        account: "Account",
        snapshot: RuleCheckpointSnapshot,
        secret_refs: tuple[str, ...] = (),
    ) -> None:
        self.account = account
        self.snapshot = snapshot
        self.secret_refs = list(secret_refs)
        self._waiters: dict[str, asyncio.Future[RuleCheckpointResponse]] = {}
        self._pending_identities: dict[str, tuple[str, str, str]] = {}

    @classmethod
    def from_job_start(
        cls,
        account: "Account",
        request: JobStartRequest | V2ActionRequest,
        *,
        secret_refs: tuple[str, ...] = (),
    ) -> "RuleCheckpointGate":
        """Require the frozen snapshot before running a governed job."""
        snapshot = (
            request.rule_snapshot
            if isinstance(request, JobStartRequest)
            else RuleCheckpointSnapshot.model_validate(request.input.get("rule_snapshot"))
            if request.input.get("rule_snapshot") is not None
            else None
        )
        if snapshot is None:
            raise ValueError("Governed job requires rule_snapshot")
        return cls(account, snapshot, secret_refs)

    async def checkpoint(
        self,
        *,
        occurrence_id: str,
        phase: Literal["before", "after"],
        job_id: str,
        case_id: str,
        step_id: str,
        context: dict[str, Any],
    ) -> RuleCheckpointResponse:
        request = RuleCheckpointRequest(
            occurrence_id=occurrence_id,
            phase=phase,
            snapshot_hash=self.snapshot.hash,
            job_id=job_id,
            case_id=case_id,
            step_id=step_id,
            context=context,
            secret_refs=self.secret_refs,
        )
        try:
            response = await _httpx_client.post(
                self.snapshot.checkpoint_url,
                headers=self.account.api_headers
                | {"X-Rule-Checkpoint-Token": self.snapshot.checkpoint_token},
                json=request.model_dump(mode="json"),
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError("Rule checkpoint request failed") from error
        result = RuleCheckpointResponse.model_validate(response.json())
        if result.snapshot_hash != self.snapshot.hash:
            raise RuntimeError("Rule checkpoint response snapshot_hash does not match")
        return result

    async def wait_for_resume(
        self,
        response: RuleCheckpointResponse,
        occurrence_id: str,
        phase: Literal["before", "after"],
    ) -> RuleCheckpointResponse:
        """Wait for a controller-pushed, validated decision without polling."""
        waiter = self._waiters.get(response.checkpoint_id)
        if waiter is None:
            waiter = asyncio.get_running_loop().create_future()
            self._waiters[response.checkpoint_id] = waiter
            self._pending_identities[response.checkpoint_id] = (
                occurrence_id,
                phase,
                response.input_hash,
            )
            _PENDING_GATES[response.checkpoint_id] = self
            delivered = _DELIVERED_DECISIONS.pop(response.checkpoint_id, None)
            if delivered is not None:
                self.resume(delivered)
        try:
            return await waiter
        finally:
            self._waiters.pop(response.checkpoint_id, None)
            self._pending_identities.pop(response.checkpoint_id, None)
            _PENDING_GATES.pop(response.checkpoint_id, None)

    def resume(self, decision: RuleCheckpointResume) -> RuleCheckpointResponse:
        """Resolve a pending in-process checkpoint from a controller push handler."""
        if decision.snapshot_hash != self.snapshot.hash:
            raise ValueError("Rule checkpoint resume snapshot_hash does not match")
        waiter = self._waiters.get(decision.checkpoint_id)
        if waiter is None:
            raise RuleCheckpointRecoveryRequired(
                f"Rule checkpoint {decision.checkpoint_id!r} has no in-process waiter"
            )
        if (
            decision.occurrence_id,
            decision.phase,
            decision.input_hash,
        ) != self._pending_identities[decision.checkpoint_id]:
            raise ValueError("Rule checkpoint resume does not match pending occurrence")
        response = RuleCheckpointResponse.model_validate(decision.model_dump())
        if not waiter.done():
            waiter.set_result(response)
        return response


def resume_rule_checkpoint(
    decision: RuleCheckpointResume,
) -> RuleCheckpointResponse | None:
    """Dispatch one explicit A2A resume decision to its live gate."""
    gate = _PENDING_GATES.get(decision.checkpoint_id)
    if gate is not None:
        return gate.resume(decision)

    # Local import breaks the Case -> rule_controls import cycle only during
    # restart recovery, when no in-process waiter exists.
    from supervaizer.case import Cases

    case = Cases().get_case(decision.case_id, decision.job_id)
    if case is None:
        _DELIVERED_DECISIONS[decision.checkpoint_id] = decision
        return None
    for state in case.metadata.get("_rule_checkpoints", {}).values():
        if (
            state.get("checkpoint_id"),
            state.get("occurrence_id"),
            state.get("phase"),
            state.get("snapshot_hash"),
            state.get("input_hash"),
        ) != (
            decision.checkpoint_id,
            decision.occurrence_id,
            decision.phase,
            decision.snapshot_hash,
            decision.input_hash,
        ):
            continue
        state["status"] = decision.status
        state["decision_id"] = decision.decision_id
        case._persist()
        return RuleCheckpointResponse.model_validate(decision.model_dump())
    raise ValueError("Rule checkpoint resume does not match persisted occurrence")


async def run_guarded_step(
    *,
    gate: RuleCheckpointGate,
    case: "Case",
    step_id: str,
    occurrence_id: str,
    before_context: dict[str, Any],
    effect: Callable[[], Awaitable[T]],
    after_context: Callable[[T], dict[str, Any]],
    advance: Callable[[T], Awaitable[Any]] | None = None,
) -> T:
    """Run an effect only after `before`, then advance only after `after` allows."""
    if not case.metadata.get("_rule_checkpoint_case_registered"):
        raise ValueError("Rule checkpoint case must be registered before a gate")
    states = case.metadata.setdefault("_rule_checkpoints", {})
    before_key = f"{occurrence_id}:before"
    after_key = f"{occurrence_id}:after"
    active_key = (case.id, occurrence_id)
    existing_before = states.get(before_key)
    context_hash = _checkpoint_input_hash(before_context)
    if existing_before is not None:
        if existing_before.get("status") != "checking":
            raise RuleCheckpointRecoveryRequired(
                "Rule checkpoint occurrence is already claimed"
            )
        if existing_before.get("context_hash") != context_hash:
            raise ValueError("Rule checkpoint retry context changed")
    if active_key in _ACTIVE_OCCURRENCES:
        raise RuleCheckpointRecoveryRequired("Rule checkpoint occurrence is active")
    after_state = states.get(after_key, {})
    if after_state.get("effect_started") or after_state.get("effect_completed"):
        raise RuleCheckpointRecoveryRequired(
            "Started rule-gated effect requires an explicit recovery handler"
        )
    _ACTIVE_OCCURRENCES.add(active_key)
    states[before_key] = {
        "occurrence_id": occurrence_id,
        "phase": "before",
        "snapshot_hash": gate.snapshot.hash,
        "context_hash": context_hash,
        "status": "checking",
    }
    case._persist()

    try:
        before = await gate.checkpoint(
            occurrence_id=occurrence_id,
            phase="before",
            job_id=case.job_id,
            case_id=case.id,
            step_id=step_id,
            context=before_context,
        )
    except Exception:
        _ACTIVE_OCCURRENCES.discard(active_key)
        raise
    states[before_key] = _checkpoint_state(before, occurrence_id, "before")
    case._persist()
    if before.status == "pause":
        before = await gate.wait_for_resume(before, occurrence_id, "before")
        states[before_key] = _checkpoint_state(before, occurrence_id, "before")
        case._persist()
    _ACTIVE_OCCURRENCES.discard(active_key)
    if before.status != "allow":
        raise RuleCheckpointBlocked(before)
    states[after_key] = {
        "occurrence_id": occurrence_id,
        "phase": "after",
        "snapshot_hash": gate.snapshot.hash,
        "effect_started": True,
        "status": "pending",
    }
    case._persist()
    result = await effect()
    states[after_key]["effect_completed"] = True
    case._persist()
    after = await gate.checkpoint(
        occurrence_id=occurrence_id,
        phase="after",
        job_id=case.job_id,
        case_id=case.id,
        step_id=step_id,
        context=after_context(result),
    )
    states[after_key] = _checkpoint_state(after, occurrence_id, "after", True)
    case._persist()
    if after.status == "pause":
        after = await gate.wait_for_resume(after, occurrence_id, "after")
        states[after_key] = _checkpoint_state(after, occurrence_id, "after", True)
        case._persist()
    if after.status != "allow":
        raise RuleCheckpointBlocked(after)
    if advance is not None:
        states[after_key]["advancement_started"] = True
        case._persist()
        await advance(result)
        states[after_key]["advancement_completed"] = True
        case._persist()
    return result


async def recover_guarded_step(
    *,
    case: "Case",
    occurrence_id: str,
    result: T,
    advance: Callable[[T], Awaitable[Any]] | None = None,
) -> T:
    """Advance a manually recovered completed effect only after its after gate allows."""
    state = case.metadata.get("_rule_checkpoints", {}).get(f"{occurrence_id}:after", {})
    if not state.get("effect_completed") or state.get("status") != "allow":
        raise RuleCheckpointRecoveryRequired("Rule checkpoint is not ready to recover")
    if state.get("advancement_started") and not state.get("advancement_completed"):
        raise RuleCheckpointRecoveryRequired("Rule checkpoint advancement is ambiguous")
    if advance is not None and not state.get("advancement_completed"):
        state["advancement_started"] = True
        case._persist()
        await advance(result)
        state["advancement_completed"] = True
        case._persist()
    return result


def _checkpoint_state(
    response: RuleCheckpointResponse,
    occurrence_id: str,
    phase: Literal["before", "after"],
    effect_completed: bool = False,
) -> dict[str, Any]:
    return {
        "checkpoint_id": response.checkpoint_id,
        "occurrence_id": occurrence_id,
        "phase": phase,
        "status": response.status,
        "snapshot_hash": response.snapshot_hash,
        "input_hash": response.input_hash,
        "effect_started": effect_completed,
        "effect_completed": effect_completed,
    }


def _checkpoint_input_hash(context: dict[str, Any]) -> str:
    payload = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
