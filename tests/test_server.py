# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control import Server
from tests.mock_api_responses import (
    SERVER_REGISTER_RESPONSE,
    SERVER_REGISTER_RESPONSE_NO_AGENTS_ERROR,
    SERVER_REGISTER_RESPONSE_UNKNOWN_AGENTS_ERROR,
    SERVER_REGISTER_RESPONSE_UNKNOWN_AND_UNKNOWN_AGENTS_ERROR,
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


def test_server_host_validator(agent_fixture, account_fixture):
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


def test_server_decrypt(server_fixture):
    unencrypted_parameters = str({"KEY": "VALUE"})
    encrypted_parameters = server_fixture.encrypt(unencrypted_parameters)
    assert encrypted_parameters is not None
    assert isinstance(encrypted_parameters, str)
    assert len(encrypted_parameters) > len(unencrypted_parameters)

    decrypted_parameters = server_fixture.decrypt(encrypted_parameters)
    assert decrypted_parameters == unencrypted_parameters


def test_server_validate_agents(server_fixture, monkeypatch):
    # Test server response with no agents
    assert not server_fixture.validate_agents(SERVER_REGISTER_RESPONSE_NO_AGENTS_ERROR)

    # Test server response with unknown agents
    assert not server_fixture.validate_agents(
        SERVER_REGISTER_RESPONSE_UNKNOWN_AGENTS_ERROR
    )

    # Test server response with known and unknown agents
    assert not server_fixture.validate_agents(
        SERVER_REGISTER_RESPONSE_UNKNOWN_AND_UNKNOWN_AGENTS_ERROR
    )
    # Simulate that decrypt method is called and returns the registered values
    monkeypatch.setattr(
        server_fixture.__class__,
        "decrypt",
        lambda self, encrypted_parameters: {
            "parameter1": "registered_value1",
            "parameter2": "registered_value2",
        },
    )
    # Test valid server response
    assert server_fixture.validate_agents(SERVER_REGISTER_RESPONSE)


@pytest.mark.current
def test_server_launch_check_registration(server_fixture, monkeypatch):
    # Mock register_server method
    mock_register_server_called = False

    def mock_register_server(self, server):
        nonlocal mock_register_server_called
        mock_register_server_called = True
        return SERVER_REGISTER_RESPONSE

    monkeypatch.setattr(
        server_fixture.account.__class__, "register_server", mock_register_server
    )

    # Simulate that decrypt method is called and returns the registered values
    monkeypatch.setattr(
        server_fixture.__class__,
        "decrypt",
        lambda self, encrypted_parameters: {
            "parameter1": "registered_value1",
            "parameter2": "registered_value2",
        },
    )

    # Mock uvicorn.run method
    mock_uvicorn_run_called = False

    def mock_uvicorn_run(app, host, port, reload, log_level):
        nonlocal mock_uvicorn_run_called
        mock_uvicorn_run_called = True
        assert host == "localhost"
        assert port == 8001
        assert not reload
        assert log_level == "info", f"log_level should be info, but is {log_level}"

    monkeypatch.setattr("uvicorn.run", mock_uvicorn_run)
    server_fixture.launch()
    assert mock_register_server_called, "register_server method should be called"
    assert mock_uvicorn_run_called, "uvicorn.run method should be called"

    # Simulate error in the server registration parameters

    # Simulate that decrypt method is called and returns incorrect parameter
    monkeypatch.setattr(
        server_fixture.__class__,
        "decrypt",
        lambda self, encrypted_parameters: {
            "invalid_parameter": "invalid_value1",
        },
    )
    with pytest.raises(ValueError):
        server_fixture.launch()
