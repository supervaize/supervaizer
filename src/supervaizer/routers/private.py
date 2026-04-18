# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Private router: Tailscale-only admin and workbench surface."""  # <-- ADDED

from __future__ import annotations

from fastapi import APIRouter, Depends

from supervaizer.access import require_tailscale  # <-- ADDED


def create_private_router() -> APIRouter:  # <-- ADDED
    """Build and return the /manage router.

    Router-level ``require_tailscale`` covers every sub-route (HTTP and WS).
    """
    from supervaizer.admin.routes import create_admin_routes
    from supervaizer.admin.workbench_routes import create_workbench_ws_routes

    private_router = APIRouter(
        prefix="/manage",
        dependencies=[Depends(require_tailscale)],  # <-- ADDED
    )

    # Admin HTML + JSON API routes
    private_router.include_router(create_admin_routes())

    # WebSocket routes inherit Tailscale dep from private_router
    private_router.include_router(create_workbench_ws_routes())

    return private_router
