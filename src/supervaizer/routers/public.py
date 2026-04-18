# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Public router: no authentication required."""  # <-- ADDED

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from supervaizer.__version__ import API_VERSION, VERSION

if TYPE_CHECKING:
    from supervaizer.server import Server

# No auth dependency — public_router is intentionally open.  # <-- ADDED
public_router = APIRouter(tags=["Public"])

_home_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "admin" / "templates")
)


def create_public_router(
    server: "Server", admin_interface: bool = True
) -> APIRouter:  # <-- ADDED
    """Build and return the public router wired to *server*.

    Includes:
    * ``GET /`` — home page
    * ``/.well-known/*`` — A2A discovery (no auth)
    """
    from supervaizer.protocol.a2a.routes import create_routes as create_a2a_routes

    router = APIRouter(tags=["Public"])

    @router.get("/", response_class=HTMLResponse)
    async def home_page(request: Request) -> HTMLResponse:  # <-- MOVED from server.py
        root_index = Path.cwd() / "index.html"
        if root_index.is_file():
            return HTMLResponse(content=root_index.read_text(encoding="utf-8"))
        base = server.public_url or f"{server.scheme}://{server.host}:{server.port}"
        return _home_templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "base": base,
                "version": VERSION,
                "api_version": API_VERSION,
                "show_admin": bool(server.api_key and admin_interface),
                "server_id": server.server_id,
            },
        )

    if server.a2a_endpoints:
        router.include_router(create_a2a_routes(server))

    return router
