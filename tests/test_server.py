# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control import Server
from tests.test_agent import agent_fixture, agent_method_fixture
from tests.test_account import account_fixture

agent_fixture = agent_fixture
agent_method_fixture = agent_method_fixture
account_fixture = account_fixture


@pytest.fixture
def server_fixture(agent_fixture, account_fixture):
    return Server(
        agents=[agent_fixture],
        host="localhost",
        port=8001,
        environment="test",
        debug=True,
        account=account_fixture,
    )


def test_server_scheme_validator(server_fixture, agent_fixture, account_fixture):
    with pytest.raises(ValueError):
        Server(
            agents=[agent_fixture],
            scheme="http://",
            host="localhost",
            port=8001,
            environment="test",
            debug=True,
            account=account_fixture,
        )


def test_server_host_validator(server_fixture, account_fixture):
    with pytest.raises(ValueError):
        Server(
            agents=[agent_fixture],
            scheme="http",
            host="http://localhost",
            port=8001,
            environment="test",
            debug=True,
            account=account_fixture,
        )


def test_server(server_fixture):
    assert isinstance(server_fixture, Server)
    assert server_fixture.host == "localhost"
    assert server_fixture.port == 8001
    assert server_fixture.url == "http://localhost:8001"
    assert server_fixture.environment == "test"
    assert server_fixture.debug
    assert len(server_fixture.agents) == 1
