# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for `supervaizer login` and for what the start does with its result."""

import stat
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from supervaizer import cli, studio_handshake
from supervaizer.studio_login import (
    DEVICE_PATH,
    StudioLoginError,
    ensure_env_file_writable,
    env_values,
    request_device_code,
    wait_for_credentials,
    write_env_file,
)

API_KEY = "sk-live-secret-0001"
DEVICE = {
    "device_code": "device-secret",
    "user_code": "ABCD-1234",
    "verification_uri_complete": "https://studio.test/cli/authorize?code=ABCD-1234",
    "expires_in": 900,
    "interval": 0,
}
CREDENTIALS = {
    "api_key": API_KEY,
    "workspace_id": "acme",
    "workspace_name": "Acme",
    "api_url": "https://app.test",
    "studio_url": "https://studio.test/w/acme",
    "workspace_auth": {
        "issuer": "https://studio.test",
        "jwks_url": "https://app.test/w/acme/api/v1/workspace-agent-grants/jwks/",
    },
}
PENDING = httpx.Response(400, json={"error": "authorization_pending"})
APPROVED = httpx.Response(200, json=CREDENTIALS)


def studio(
    token_answers: list[httpx.Response], device: httpx.Response | None = None
) -> httpx.Client:
    """A Studio that gives one device code, then the token answers in order."""
    answers = iter(token_answers)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == DEVICE_PATH:
            return device or httpx.Response(201, json=DEVICE)
        return next(answers)

    return httpx.Client(
        base_url="https://app.test", transport=httpx.MockTransport(handler)
    )


def test_login_waits_while_pending_then_returns_the_credentials() -> None:
    client = studio([PENDING, PENDING, APPROVED])
    device = request_device_code(client)

    assert wait_for_credentials(client, device) == CREDENTIALS


def test_denied_login_stops_with_an_error() -> None:
    denied = httpx.Response(400, json={"error": "access_denied"})

    with pytest.raises(StudioLoginError, match="denied"):
        wait_for_credentials(studio([PENDING, denied]), DEVICE)


def test_login_stops_when_the_code_expires() -> None:
    ticks = iter(range(0, 10_000, 600))

    with pytest.raises(StudioLoginError, match="expired"):
        wait_for_credentials(
            studio([PENDING] * 5),
            DEVICE,
            sleep=lambda _: None,
            clock=lambda: float(next(ticks)),
        )


def test_slow_down_makes_the_poll_slower() -> None:
    waits: list[float] = []
    slow_down = httpx.Response(400, json={"error": "slow_down"})

    wait_for_credentials(studio([slow_down, APPROVED]), DEVICE, sleep=waits.append)

    assert waits == [0.0, 5.0]


def test_a_studio_without_cli_login_gives_a_clear_error() -> None:
    with pytest.raises(StudioLoginError, match="does not support"):
        request_device_code(studio([], device=httpx.Response(404)))


def test_an_approval_address_that_is_not_a_web_page_is_refused() -> None:
    device = {**DEVICE, "verification_uri_complete": "file:///etc/passwd"}

    with pytest.raises(StudioLoginError, match="not a web page"):
        request_device_code(studio([], device=httpx.Response(201, json=device)))


def test_a_value_with_a_line_break_is_refused() -> None:
    with pytest.raises(StudioLoginError, match="not valid"):
        env_values({**CREDENTIALS, "workspace_id": "acme\nEVIL=1"})


def test_a_missing_field_is_an_error_not_a_default() -> None:
    with pytest.raises(StudioLoginError, match="api_key"):
        env_values({**CREDENTIALS, "api_key": ""})


def test_env_file_is_private_and_keeps_the_other_lines(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env_file(env_file, {"SUPERVAIZE_API_KEY": "first"})
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600

    env_file.write_text("OPENAI_KEY=keep\nSUPERVAIZE_API_KEY=first\n", encoding="utf-8")
    write_env_file(env_file, {"SUPERVAIZE_API_KEY": "second"})

    assert env_file.read_text(encoding="utf-8") == (
        "OPENAI_KEY=keep\nSUPERVAIZE_API_KEY=second\n"
    )


def test_envrc_lines_have_an_export(tmp_path: Path) -> None:
    envrc = tmp_path / ".envrc"
    envrc.write_text("export SUPERVAIZE_API_KEY=first\n", encoding="utf-8")

    write_env_file(envrc, {"SUPERVAIZE_API_KEY": "second"})

    assert envrc.read_text(encoding="utf-8") == "export SUPERVAIZE_API_KEY=second\n"


def use_studio(monkeypatch: pytest.MonkeyPatch, client: httpx.Client) -> None:
    """Make the login command talk to `client`, with no call to PyPI."""
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(cli, "_check_version", lambda: (True, None))


def test_login_command_writes_the_file_and_prints_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    use_studio(monkeypatch, studio([PENDING, APPROVED]))
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    env_file = tmp_path / ".env"

    result = CliRunner().invoke(cli.app, ["login", "--env-file", str(env_file)])

    assert result.exit_code == 0, result.output
    assert "Logged in." in result.output
    assert opened == [DEVICE["verification_uri_complete"]]
    assert "The page must show this code" in result.output
    assert "1234" in result.output
    assert API_KEY not in result.output
    assert f"SUPERVAIZE_API_KEY={API_KEY}" in env_file.read_text(encoding="utf-8")
    assert "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true" in env_file.read_text(
        encoding="utf-8"
    )


def test_ensure_env_file_writable_rejects_a_missing_parent_directory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "missing" / ".env"
    with pytest.raises(StudioLoginError, match="does not exist"):
        ensure_env_file_writable(target)


def test_ensure_env_file_writable_rejects_a_non_utf8_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"\xff\xfe")
    with pytest.raises(StudioLoginError, match="UTF-8"):
        ensure_env_file_writable(env_file)


def test_login_command_fails_before_studio_when_env_file_path_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def never_called(**_: object) -> httpx.Client:
        calls.append("client")
        raise AssertionError("Studio client must not start when the env file is invalid")

    monkeypatch.setattr(cli.httpx, "Client", never_called)
    monkeypatch.setattr(cli, "_check_version", lambda: (True, None))
    env_file = tmp_path / "no-such-dir" / ".env"

    result = CliRunner().invoke(
        cli.app, ["login", "--no-browser", "--env-file", str(env_file)]
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert calls == []


def test_login_command_fails_and_writes_nothing_when_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    denied = httpx.Response(400, json={"error": "access_denied"})
    use_studio(monkeypatch, studio([denied]))
    env_file = tmp_path / ".env"

    result = CliRunner().invoke(
        cli.app, ["login", "--no-browser", "--env-file", str(env_file)]
    )

    assert result.exit_code == 1
    assert "denied in Studio" in result.output
    assert not env_file.exists()


def test_start_refuses_an_env_file_that_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_check_version", lambda: (True, None))

    result = CliRunner().invoke(
        cli.app, ["start", "--env-file", str(tmp_path / "missing.env")]
    )

    assert result.exit_code == 1
    assert "not found" in result.output


def test_start_uses_runtime_keys_from_env_file_when_flags_use_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "studio.env"
    env_file.write_text(
        "SUPERVAIZER_HOST=10.0.0.1\nSUPERVAIZER_PORT=9001\n", encoding="utf-8"
    )
    captured: dict[str, object] = {}

    def capture_fallback(
        host: str, port: int, debug: bool, environment: str, log_level: str
    ) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.chdir(tmp_path)
    for name in (
        "SUPERVAIZER_HOST",
        "SUPERVAIZER_PORT",
        "SUPERVAIZER_PUBLIC_URL",
        "SUPERVAIZER_DEBUG",
        "SUPERVAIZER_RELOAD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "_check_version", lambda: (True, None))
    monkeypatch.setattr(cli, "_launch_local_fallback", capture_fallback)
    monkeypatch.setattr(cli, "_resolve_start_script", lambda _path, _local: ("x", True))

    result = CliRunner().invoke(
        cli.app, ["start", "--local", "--env-file", str(env_file)]
    )

    assert result.exit_code == 0, result.output
    assert captured == {"host": "10.0.0.1", "port": 9001}


def test_start_explicit_host_overrides_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SUPERVAIZER_HOST=10.0.0.1\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def capture_fallback(
        host: str, port: int, debug: bool, environment: str, log_level: str
    ) -> None:
        captured["host"] = host

    monkeypatch.setattr(cli, "_check_version", lambda: (True, None))
    monkeypatch.setattr(cli, "_launch_local_fallback", capture_fallback)
    monkeypatch.setattr(cli, "_resolve_start_script", lambda _path, _local: ("x", True))

    result = CliRunner().invoke(
        cli.app,
        [
            "start",
            "--local",
            "--env-file",
            str(env_file),
            "--host",
            "127.0.0.1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {"host": "127.0.0.1"}


def test_environment_file_sets_only_the_variables_that_are_not_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SV_TEST_NEW=file\nexport SV_TEST_SET=file\n", encoding="utf-8")
    monkeypatch.delenv("SV_TEST_NEW", raising=False)
    monkeypatch.setenv("SV_TEST_SET", "shell")

    cli._load_environment_file(str(env_file))

    assert cli.os.environ["SV_TEST_NEW"] == "file"
    assert cli.os.environ["SV_TEST_SET"] == "shell"
    monkeypatch.delenv("SV_TEST_NEW")


def test_handshake_logs_the_studio_page_of_each_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines: list[str] = []

    class Log:
        def success(self, message: str) -> None:
            lines.append(message)

    monkeypatch.setattr(studio_handshake, "log", Log())
    agents: list[Any] = [
        {"id": "1", "slug": "new", "studio_url": "https://studio.test/w/acme/agents/1"},
        {"id": "2", "slug": "old-studio"},
    ]

    studio_handshake._log_agent_pages({"workspace_authorization": {"agents": agents}})
    studio_handshake._log_agent_pages({})

    assert len(lines) == 1
    assert "https://studio.test/w/acme/agents/1" in lines[0]
