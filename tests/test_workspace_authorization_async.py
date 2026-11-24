# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
from types import SimpleNamespace

import pytest

from supervaizer.contracts import V2WorkspaceContext
from supervaizer.workspace_authorization import (
    WorkspaceAuthorizationError,
    verify_workspace_authorization_for_request_async,
)


def test_async_workspace_verification_honors_optional_configuration() -> None:
    server = SimpleNamespace(workspace_authorization=None)
    workspace = V2WorkspaceContext(id="workspace-1")

    assert asyncio.run(
        verify_workspace_authorization_for_request_async(
            server=server,
            token=None,
            required_scopes=["read"],
            request_workspace=workspace,
            agent_slug="agent",
            require_configured=False,
        )
    ) is None
    with pytest.raises(WorkspaceAuthorizationError) as raised:
        asyncio.run(
            verify_workspace_authorization_for_request_async(
                server=server,
                token=None,
                required_scopes=["read"],
                request_workspace=workspace,
                agent_slug="agent",
            )
        )
    assert raised.value.code == "workspace_authorization_not_configured"
