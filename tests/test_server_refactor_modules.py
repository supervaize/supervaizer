# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import Any

import pytest

import supervaizer.scheduled_steps as scheduled_steps
import supervaizer.server as server_module
import supervaizer.server_config as server_config
import supervaizer.server_info as server_info
from supervaizer import Server
from supervaizer.common import ApiSuccess
from supervaizer.server_registration import build_server_registration_info
from supervaizer.studio_handshake import validate_registration_handshake


def test_server_module_reexports_scheduled_step_helpers() -> None:
    assert (
        server_module._execute_scheduled_method
        is scheduled_steps._execute_scheduled_method
    )
    assert (
        server_module._run_scheduled_step_loop
        is scheduled_steps._run_scheduled_step_loop
    )


def test_server_module_reexports_config_helpers() -> None:
    assert server_module._env_bool is server_config._env_bool
    assert (
        server_module._controller_key_fingerprint
        is server_config._controller_key_fingerprint
    )


def test_server_module_reexports_server_info_helpers() -> None:
    assert server_module.ServerInfo is server_info.ServerInfo
    assert (
        server_module.get_server_info_from_storage
        is server_info.get_server_info_from_storage
    )
    assert (
        server_module.get_server_info_from_live is server_info.get_server_info_from_live
    )


def test_execute_scheduled_method_calls_dotted_function() -> None:
    result = scheduled_steps._execute_scheduled_method(
        "tests.test_server_refactor_modules._scheduled_step_target",
        {"value": "ok"},
    )

    assert result == "scheduled-ok"


def test_resolve_workspace_authorization_settings_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", "yes")
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_ISSUER", "https://studio.test")
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_AUDIENCE", "server-audience")
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL", "https://jwks.test")
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_LEEWAY_SECONDS", "9")

    settings = server_config._resolve_workspace_authorization_settings(None)

    assert settings.enabled is True
    assert settings.issuer == "https://studio.test"
    assert settings.audience == "server-audience"
    assert settings.jwks_url == "https://jwks.test"
    assert settings.leeway_seconds == 9


def test_get_server_info_from_live_uses_server_start_time(
    server_fixture: Server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_ENVIRONMENT", "module-test")
    object.__setattr__(server_fixture, "_start_time", 123.0)

    info = server_info.get_server_info_from_live(server_fixture)

    assert info.start_time == 123.0
    assert info.environment == "module-test"
    assert info.agents == [
        {
            "name": server_fixture.agents[0].name,
            "description": server_fixture.agents[0].description,
            "version": server_fixture.agents[0].version,
            "api_path": server_fixture.agents[0].path,
            "slug": server_fixture.agents[0].slug,
            "instructions_path": server_fixture.agents[0].instructions_path,
        }
    ]


def test_server_info_storage_round_trip(
    server_fixture: Server,
    storage_manager: Any,
) -> None:
    storage_manager.reset_storage()

    server_info.save_server_info_to_storage(server_fixture)
    stored_info = server_info.get_server_info_from_storage()

    assert stored_info is not None
    assert stored_info.id == server_info.SERVER_INFO_ID
    assert stored_info.host == server_fixture.host


def test_registration_builder_matches_server_property(server_fixture: Server) -> None:
    assert (
        build_server_registration_info(server_fixture)
        == server_fixture.registration_info
    )


def test_validate_registration_handshake_function_accepts_key_match(
    server_fixture: Server,
) -> None:
    result = ApiSuccess(
        message="POST Event SERVER_REGISTER sent",
        detail={
            "object": {
                "supervaizer_handshake": {
                    "server_id": "server-1",
                    "controller_api_key_match": True,
                }
            }
        },
    )

    validate_registration_handshake(server_fixture, result)


def _scheduled_step_target(value: str) -> str:
    return f"scheduled-{value}"
