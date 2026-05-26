# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from supervaizer.common import log

if TYPE_CHECKING:
    from supervaizer.server import Server

SCHEDULED_STEP_POLL_SECONDS = 60


def _execute_scheduled_method(method_path: str, params: dict[str, Any]) -> Any:
    """Execute a method by its full dotted path."""
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
            for _case, _step_index, update in due_steps:
                if not update.scheduled_method:
                    continue
                try:
                    object.__setattr__(update, "scheduled_status", "executing")
                    log.info(f"[Scheduled step] Executing: {update.name}")
                    _execute_scheduled_method(
                        update.scheduled_method,
                        update.scheduled_params or {},
                    )
                    object.__setattr__(update, "scheduled_status", "completed")
                    log.info(f"[Scheduled step] Completed: {update.name}")
                except Exception as exc:
                    object.__setattr__(update, "scheduled_status", "failed")
                    log.error(f"[Scheduled step] Failed: {update.name}: {exc}")
        except Exception as exc:
            log.error(f"[Scheduled step loop] Error: {exc}")
