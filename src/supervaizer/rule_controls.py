# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Explicit SDK helpers for Studio rule checkpoint gates.

Agents must put cooperative effects inside ``run_guarded_step`` and declare
business-secret paths in ``secret_refs``. An after gate cannot undo a completed
external effect, and ambiguous recovery never replays one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import asyncio
import contextlib
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
# Early decisions wait milliseconds for their waiter, so past this many newer
# deliveries an entry is abandoned. Switch to a TTL if a controller needs more.
_DELIVERED_DECISIONS_LIMIT = 1024
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
        *,
        agent_slug: str,
    ) -> None:
        self.account = account
        self.snapshot = snapshot
        self.agent_slug = agent_slug
        self.secret_refs = list(secret_refs)
        self._waiters: dict[str, asyncio.Future[RuleCheckpointResponse]] = {}
        self._pending_identities: dict[str, tuple[str, str, str, str, str]] = {}

    @classmethod
    def from_job_start(
        cls,
        account: "Account",
        request: JobStartRequest | V2ActionRequest,
        *,
        secret_refs: tuple[str, ...] = (),
        agent_slug: str | None = None,
    ) -> "RuleCheckpointGate":
        """Require the frozen snapshot before running a governed job.

        A v1 ``JobStartRequest`` names no agent, so pass ``agent_slug``; a
        ``V2ActionRequest`` carries its own.
        """
        if isinstance(request, JobStartRequest):
            snapshot = request.rule_snapshot
        else:
            raw_snapshot = request.input.get("rule_snapshot")
            snapshot = (
                RuleCheckpointSnapshot.model_validate(raw_snapshot)
                if raw_snapshot is not None
                else None
            )
            agent_slug = request.agent_slug
        if snapshot is None:
            raise ValueError("Governed job requires rule_snapshot")
        if not agent_slug:
            raise ValueError("Governed job requires agent_slug")
        return cls(account, snapshot, secret_refs, agent_slug=agent_slug)

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
            # The snapshot arrives in request input, so its checkpoint_url is not
            # trusted with controller credentials: post only to the configured Studio.
            response = await _httpx_client.post(
                f"{self.account.api_url}/api/v1/rule-checkpoints/",
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
        *,
        job_id: str,
        case_id: str,
    ) -> RuleCheckpointResponse:
        """Wait for a controller-pushed, validated decision without polling."""
        waiter = self._waiters.get(response.checkpoint_id)
        if waiter is None:
            waiter = asyncio.get_running_loop().create_future()
            self._waiters[response.checkpoint_id] = waiter
            self._pending_identities[response.checkpoint_id] = (
                job_id,
                case_id,
                occurrence_id,
                phase,
                response.input_hash,
            )
            _PENDING_GATES[response.checkpoint_id] = self
            delivered = _DELIVERED_DECISIONS.pop(response.checkpoint_id, None)
            if delivered is not None:
                # A mismatched early decision is discarded; keep waiting for a valid one.
                with contextlib.suppress(ValueError):
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
        if decision.agent_slug != self.agent_slug:
            raise ValueError("Rule checkpoint resume is for another agent")
        waiter = self._waiters.get(decision.checkpoint_id)
        if waiter is None:
            raise RuleCheckpointRecoveryRequired(
                f"Rule checkpoint {decision.checkpoint_id!r} has no in-process waiter"
            )
        if (
            decision.job_id,
            decision.case_id,
            decision.occurrence_id,
            decision.phase,
            decision.input_hash,
        ) != self._pending_identities[decision.checkpoint_id]:
            raise ValueError("Rule checkpoint resume does not match pending occurrence")
        response = RuleCheckpointResponse.model_validate(decision.model_dump())
        # A sync v1 job method runs its own event loop in a worker thread, so
        # settle the waiter on its loop, not on the handler's.
        waiter.get_loop().call_soon_threadsafe(_settle, waiter, response)
        return response


def _settle(
    waiter: asyncio.Future[RuleCheckpointResponse], response: RuleCheckpointResponse
) -> None:
    if not waiter.done():
        waiter.set_result(response)


def resume_rule_checkpoint(
    decision: RuleCheckpointResume,
) -> RuleCheckpointResponse | None:
    """Persist one explicit A2A resume decision, then wake its waiter."""
    # Local import breaks the Case -> rule_controls import cycle.
    from supervaizer.case import Cases

    case = Cases().get_case(decision.case_id, decision.job_id)
    if case is None:
        gate = _PENDING_GATES.get(decision.checkpoint_id)
        if gate is not None:
            return gate.resume(decision)
        _retain_decision(decision)
        return None
    if case.metadata.get("_rule_checkpoint_agent_slug") != decision.agent_slug:
        raise ValueError("Rule checkpoint resume is for another agent")
    for state in case.metadata.get("_rule_checkpoints", {}).values():
        if "checkpoint_id" not in state and (
            state.get("occurrence_id"),
            state.get("phase"),
            state.get("snapshot_hash"),
        ) == (decision.occurrence_id, decision.phase, decision.snapshot_hash):
            # The checkpoint request has not returned yet; its waiter takes this.
            _retain_decision(decision)
            return None
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
        # Persist before the waiter wakes and before the handler acknowledges, so
        # a restart in between still finds the decision on the case.
        state["status"] = decision.status
        state["decision_id"] = decision.decision_id
        case._persist()
        # Hands the decision to a live waiter, or keeps it for a later one.
        _retain_decision(decision)
        return RuleCheckpointResponse.model_validate(decision.model_dump())
    raise ValueError("Rule checkpoint resume does not match persisted occurrence")


def _retain_decision(decision: RuleCheckpointResume) -> None:
    """Keep a decision for a waiter that registers later, evicting the oldest."""
    _DELIVERED_DECISIONS[decision.checkpoint_id] = decision
    if len(_DELIVERED_DECISIONS) > _DELIVERED_DECISIONS_LIMIT:
        del _DELIVERED_DECISIONS[next(iter(_DELIVERED_DECISIONS))]
    # A waiter in another thread can register, and find the cache empty, after
    # the caller looked for its gate. Hand the decision over; pop picks one side.
    gate = _PENDING_GATES.get(decision.checkpoint_id)
    if (
        gate is not None
        and _DELIVERED_DECISIONS.pop(decision.checkpoint_id, None) is not None
    ):
        gate.resume(decision)


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
    owner = case.metadata.setdefault("_rule_checkpoint_agent_slug", gate.agent_slug)
    if owner != gate.agent_slug:
        raise ValueError("Rule checkpoint case belongs to another agent")
    states = case.metadata.setdefault("_rule_checkpoints", {})
    before_key = f"{occurrence_id}:before"
    after_key = f"{occurrence_id}:after"
    active_key = (case.id, occurrence_id)
    existing_before = states.get(before_key)
    context_hash = _checkpoint_input_hash(before_context)
    before_allowed = False
    if existing_before is not None:
        if existing_before.get("context_hash") != context_hash:
            raise ValueError("Rule checkpoint retry context changed")
        if existing_before.get("snapshot_hash") != gate.snapshot.hash:
            raise ValueError("Rule checkpoint retry snapshot changed")
        if existing_before.get("step_id") != step_id:
            raise ValueError("Rule checkpoint retry step changed")
        before_allowed = existing_before.get("status") == "allow"
        if before_allowed and (
            states.get(after_key, {}).get("effect_started")
            or states.get(after_key, {}).get("effect_completed")
        ):
            raise RuleCheckpointRecoveryRequired(
                "Rule checkpoint occurrence is already claimed"
            )
        if not before_allowed and existing_before.get("status") != "checking":
            raise RuleCheckpointRecoveryRequired(
                "Rule checkpoint occurrence is already claimed"
            )
    if active_key in _ACTIVE_OCCURRENCES:
        raise RuleCheckpointRecoveryRequired("Rule checkpoint occurrence is active")
    after_state = states.get(after_key, {})
    if after_state.get("effect_started") or after_state.get("effect_completed"):
        raise RuleCheckpointRecoveryRequired(
            "Started rule-gated effect requires an explicit recovery handler"
        )
    _ACTIVE_OCCURRENCES.add(active_key)
    try:
        if not before_allowed:
            states[before_key] = {
                "occurrence_id": occurrence_id,
                "phase": "before",
                "snapshot_hash": gate.snapshot.hash,
                "step_id": step_id,
                "context_hash": context_hash,
                "status": "checking",
            }
            case._persist()
            before = await gate.checkpoint(
                occurrence_id=occurrence_id,
                phase="before",
                job_id=case.job_id,
                case_id=case.id,
                step_id=step_id,
                context=before_context,
            )
            states[before_key] = _checkpoint_state(before, occurrence_id, "before")
            states[before_key]["step_id"] = step_id
            states[before_key]["context_hash"] = context_hash
            case._persist()
            if before.status == "pause":
                before = await gate.wait_for_resume(
                    before, occurrence_id, "before", job_id=case.job_id, case_id=case.id
                )
                states[before_key] = _checkpoint_state(before, occurrence_id, "before")
                states[before_key]["step_id"] = step_id
                states[before_key]["context_hash"] = context_hash
                case._persist()
            if before.status != "allow":
                raise RuleCheckpointBlocked(before)
        states[after_key] = {
            "occurrence_id": occurrence_id,
            "phase": "after",
            "snapshot_hash": gate.snapshot.hash,
            "step_id": step_id,
            "effect_started": True,
            "status": "pending",
        }
        case._persist()
        result = await effect()
        after_context_value = after_context(result)
        states[after_key]["effect_completed"] = True
        states[after_key]["context_hash"] = _checkpoint_input_hash(after_context_value)
        case._persist()
        after = await gate.checkpoint(
            occurrence_id=occurrence_id,
            phase="after",
            job_id=case.job_id,
            case_id=case.id,
            step_id=step_id,
            context=after_context_value,
        )
        states[after_key] = _checkpoint_state(after, occurrence_id, "after", True)
        states[after_key]["step_id"] = step_id
        states[after_key]["context_hash"] = _checkpoint_input_hash(after_context_value)
        case._persist()
        if after.status == "pause":
            after = await gate.wait_for_resume(
                after, occurrence_id, "after", job_id=case.job_id, case_id=case.id
            )
            states[after_key] = _checkpoint_state(after, occurrence_id, "after", True)
            states[after_key]["step_id"] = step_id
            states[after_key]["context_hash"] = _checkpoint_input_hash(
                after_context_value
            )
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
    finally:
        _ACTIVE_OCCURRENCES.discard(active_key)


async def recover_guarded_step(
    *,
    gate: RuleCheckpointGate | None = None,
    case: "Case",
    occurrence_id: str,
    result: T,
    after_context: Callable[[T], dict[str, Any]] | None = None,
    advance: Callable[[T], Awaitable[Any]] | None = None,
) -> T:
    """Retry a pending after gate, then advance a recovered completed effect once."""
    state = case.metadata.get("_rule_checkpoints", {}).get(f"{occurrence_id}:after", {})
    if not state.get("effect_completed"):
        raise RuleCheckpointRecoveryRequired("Rule checkpoint is not ready to recover")
    active_key = (case.id, occurrence_id)
    if active_key in _ACTIVE_OCCURRENCES:
        raise RuleCheckpointRecoveryRequired("Rule checkpoint occurrence is active")
    if state.get("advancement_started") and not state.get("advancement_completed"):
        raise RuleCheckpointRecoveryRequired("Rule checkpoint advancement is ambiguous")
    _ACTIVE_OCCURRENCES.add(active_key)
    try:
        if state.get("status") == "pending":
            if gate is None or after_context is None:
                raise RuleCheckpointRecoveryRequired(
                    "Pending after checkpoint requires its gate and context"
                )
            if state.get("snapshot_hash") != gate.snapshot.hash:
                raise ValueError("Rule checkpoint recovery snapshot changed")
            context = after_context(result)
            if state.get("context_hash") != _checkpoint_input_hash(context):
                raise ValueError("Rule checkpoint recovery context changed")
            after = await gate.checkpoint(
                occurrence_id=occurrence_id,
                phase="after",
                job_id=case.job_id,
                case_id=case.id,
                step_id=state["step_id"],
                context=context,
            )
            state.update(_checkpoint_state(after, occurrence_id, "after", True))
            state["context_hash"] = _checkpoint_input_hash(context)
            case._persist()
            if after.status == "pause":
                after = await gate.wait_for_resume(
                    after, occurrence_id, "after", job_id=case.job_id, case_id=case.id
                )
                state.update(_checkpoint_state(after, occurrence_id, "after", True))
                state["context_hash"] = _checkpoint_input_hash(context)
                case._persist()
        if state.get("status") != "allow":
            raise RuleCheckpointRecoveryRequired(
                "Rule checkpoint is not ready to recover"
            )
        if advance is not None and not state.get("advancement_completed"):
            state["advancement_started"] = True
            case._persist()
            await advance(result)
            state["advancement_completed"] = True
            case._persist()
        return result
    finally:
        _ACTIVE_OCCURRENCES.discard(active_key)


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
