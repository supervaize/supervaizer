# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from supervaizer.common import log
from supervaizer.job import Jobs

if TYPE_CHECKING:
    from supervaizer.server import Server

SCHEDULED_STEP_POLL_SECONDS = 60


def _execute_scheduled_method(
    method_path: str,
    params: dict[str, Any],
    allowed_methods: set[str] | None = None,
) -> Any:
    """Execute a method by its full dotted path.

    Args:
        method_path: Dotted path of the callable to invoke.
        params: Keyword arguments passed to the callable.
        allowed_methods: If provided, ``method_path`` must be a member of this
            allow-list (the agent's declared method paths); otherwise execution
            is refused. This prevents a tampered or malformed scheduled step
            from importing and calling an arbitrary dotted path (unsafe
            reflection). When ``None`` (e.g. legacy/direct callers) no
            allow-list is enforced.
    """
    if allowed_methods is not None and method_path not in allowed_methods:
        raise ValueError(
            f"Scheduled method {method_path!r} is not an allowed agent method"
        )
    module_name, func_name = method_path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[func_name])
    method = getattr(module, func_name)
    return method(**params)


async def _run_scheduled_step_loop(server: Server) -> None:
    """Poll for due scheduled steps and execute them."""
    from supervaizer.case import Cases

    while True:
        await asyncio.sleep(SCHEDULED_STEP_POLL_SECONDS)
        try:
            cases = Cases()
            due_steps = cases.get_due_scheduled_steps()
            # Per-agent declared-method allow-lists. A scheduled step may only
            # invoke methods declared by the agent that owns its job, so a
            # tampered/malformed step cannot reach another agent's methods.
            agent_methods: dict[str, set[str]] = {
                agent.name: agent._declared_method_paths() for agent in server.agents
            }
            jobs = Jobs()
            for _case, _step_index, update in due_steps:
                if not update.scheduled_method:
                    continue
                # Scope the allow-list to the owning job's agent. If the owning
                # job cannot be resolved, fail the step rather than falling back
                # to a broader allow-list — an orphaned step must not be able to
                # invoke another agent's methods.
                owning_job = jobs.get_job(_case.job_id, include_persisted=True)
                if owning_job is None:
                    object.__setattr__(update, "scheduled_status", "failed")
                    log.warning(
                        f"[Scheduled step] Skipping {update.name}: owning job "
                        f"{_case.job_id} could not be resolved"
                    )
                    continue
                allowed_methods = agent_methods.get(owning_job.agent_name, set())
                try:
                    object.__setattr__(update, "scheduled_status", "executing")
                    log.info(f"[Scheduled step] Executing: {update.name}")
                    _execute_scheduled_method(
                        update.scheduled_method,
                        update.scheduled_params or {},
                        allowed_methods=allowed_methods,
                    )
                    object.__setattr__(update, "scheduled_status", "completed")
                    log.info(f"[Scheduled step] Completed: {update.name}")
                except Exception as exc:
                    object.__setattr__(update, "scheduled_status", "failed")
                    log.error(f"[Scheduled step] Failed: {update.name}: {exc}")
        except Exception as exc:
            log.error(f"[Scheduled step loop] Error: {exc}")
