# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize Agent Studio identity edge cases before lifecycle changes."""

from typing import Any
from unittest.mock import Mock

import pytest

from supervaizer.agent import Agent
from supervaizer.common import ApiSuccess


class FalseyAccount:
    """Account sentinel that preserves legacy falsey-account behavior."""

    def __bool__(self) -> bool:
        return False

    def get_agent_by(self, **kwargs: Any) -> ApiSuccess:
        raise AssertionError(f"Unexpected Studio lookup: {kwargs}")


def _server(account: Any) -> Mock:
    server = Mock()
    server.supervisor_account = account
    return server


def _success(detail: dict[str, Any]) -> ApiSuccess:
    return ApiSuccess(message="ok", detail=detail, code=200)


def test_update_replaces_empty_agent_id_with_studio_agent_id() -> None:
    agent = Agent(name="Identity Edge Agent", server_agent_id="")
    account = Mock()
    account.get_agent_by.return_value = _success({"id": "studio-agent-1"})

    updated = agent.update_agent_from_server(_server(account))

    assert updated is agent
    assert agent.server_agent_id == "studio-agent-1"
    account.get_agent_by.assert_called_once_with(agent_slug=agent.slug)


def test_update_rejects_empty_agent_id_when_studio_omits_agent_id() -> None:
    agent = Agent(name="Identity Edge Agent", server_agent_id="")
    account = Mock()
    account.get_agent_by.return_value = _success({"status": "ready"})

    with pytest.raises(ValueError, match="response did not include agent id"):
        agent.update_agent_from_server(_server(account))


def test_update_raises_when_studio_provider_returns_none() -> None:
    agent = Agent(name="Identity Edge Agent")
    account = Mock()
    account.get_agent_by.return_value = None

    with pytest.raises(AttributeError):
        agent.update_agent_from_server(_server(account))


def test_update_skips_falsey_studio_account_without_lookup() -> None:
    agent = Agent(name="Identity Edge Agent")

    updated = agent.update_agent_from_server(_server(FalseyAccount()))

    assert updated is None
