# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Pin CLI file and startup behavior before extracting its steps."""

import os
from pathlib import Path
from typing import cast
from unittest.mock import mock_open, patch

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from supervaizer import cli
from supervaizer.server import Server


@pytest.fixture(autouse=True)
def isolated_cli_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch.object(cli, "_check_version", return_value=(True, None))


@pytest.mark.parametrize("choice", ["n\n", "y\n"])
def test_refresh_instructions_preserves_or_replaces_an_existing_file(
    tmp_path: Path, choice: str
) -> None:
    target = tmp_path / "supervaize_instructions.html"
    target.write_text("existing documentation")

    result = CliRunner().invoke(
        cli.app, ["scaffold", "refresh-instructions"], input=choice
    )

    assert result.exit_code == 0
    if choice == "n\n":
        assert target.read_text() == "existing documentation"
        assert "Cancelled." in result.stdout
    else:
        assert "existing documentation" not in target.read_text()
        assert "Created fresh instructions template" in result.stdout


def test_refresh_force_skips_the_prompt(tmp_path: Path, mocker: MockerFixture) -> None:
    target = tmp_path / "supervaize_instructions.html"
    target.write_text("old")
    prompt = mocker.patch.object(cli.Confirm, "ask")

    result = CliRunner().invoke(
        cli.app, ["scaffold", "refresh-instructions", "--force"]
    )

    assert result.exit_code == 0
    assert target.read_text() != "old"
    assert "Deleted" in result.stdout
    prompt.assert_not_called()


def test_refresh_uses_the_control_file_environment_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "controller"
    directory.mkdir()
    monkeypatch.setenv("SUPERVAIZER_SCRIPT_PATH", str(directory / "control.py"))

    result = CliRunner().invoke(cli.app, ["scaffold", "refresh-instructions"])

    assert result.exit_code == 0
    assert (directory / "supervaize_instructions.html").read_text()
    assert "Created fresh instructions template" in result.stdout


def test_refresh_custom_filename_still_creates_the_fixed_template_name(
    tmp_path: Path,
) -> None:
    custom = tmp_path / "custom.html"
    custom.write_text("old custom file")

    result = CliRunner().invoke(
        cli.app,
        ["scaffold", "refresh-instructions", "--output-path", str(custom), "--force"],
    )

    assert result.exit_code == 0
    assert not custom.exists()
    assert (tmp_path / "supervaize_instructions.html").read_text()
    assert str(custom) in result.stdout.replace("\n", "")


@pytest.mark.parametrize("public_url", [None, "https://cli.example.test"])
def test_start_selects_the_first_server_and_keeps_override_rules(
    tmp_path: Path, mocker: MockerFixture, public_url: str | None
) -> None:
    control = tmp_path / "control.py"
    control.write_text(
        "from supervaizer.server import Server\n"
        "z_server = Server(agents=[], host='old-z', port=12)\n"
        "a_server = Server(agents=[], host='old-a', port=13, "
        "public_url='https://script.example.test')\n"
    )
    launch = mocker.patch.object(Server, "launch", autospec=True)
    args = ["start", "--host", "127.0.0.2", "--port", "9010"]
    if public_url is not None:
        args.extend(["--public-url", public_url])
    args.append(str(control))

    with patch.dict(os.environ, {}, clear=True):
        result = CliRunner().invoke(cli.app, args)

    assert result.exit_code == 0, result.stdout
    launch.assert_called_once()
    selected = cast(Server, launch.call_args.args[0])
    assert selected.host == "127.0.0.2"
    assert selected.port == 9010
    assert selected.public_url == (public_url or "https://script.example.test")
    assert launch.call_args.kwargs == {"log_level": "INFO"}


def test_start_rejects_a_control_script_without_a_server(tmp_path: Path) -> None:
    control = tmp_path / "control.py"
    control.write_text("ordinary_value = 1\n")

    with patch.dict(os.environ, {}, clear=True):
        result = CliRunner().invoke(cli.app, ["start", str(control)])

    assert result.exit_code == 1
    assert "No Server instance found" in result.stdout


@pytest.mark.parametrize("missing_loader", [False, True])
def test_start_reports_an_unloadable_script(
    tmp_path: Path, mocker: MockerFixture, missing_loader: bool
) -> None:
    control = tmp_path / "control.py"
    control.write_text("ordinary_value = 1\n")
    spec = mocker.Mock(loader=None) if missing_loader else None
    mocker.patch("importlib.util.spec_from_file_location", return_value=spec)

    with patch.dict(os.environ, {}, clear=True):
        result = CliRunner().invoke(cli.app, ["start", str(control)])

    assert result.exit_code == 1
    assert "Could not load" in result.stdout


def test_local_start_parses_mocked_configuration_without_overriding_existing_values(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocked_file = mock_open(
        read_data="\n# comment\ninvalid\n=ignored\n SPACE = trimmed \nEXISTING=replace\nHAS_EQUALS=x=y\n"
    )
    mocker.patch.object(cli, "open", mocked_file, create=True)
    mocker.patch.object(
        cli.os.path, "isfile", side_effect=lambda path: str(path).endswith(".env")
    )
    launch = mocker.patch.object(Server, "launch", autospec=True)

    with patch.dict(
        os.environ, {"EXISTING": "keep", "SUPERVAIZER_API_KEY": "dummy-key"}, clear=True
    ):
        result = CliRunner().invoke(cli.app, ["start", "--local", "--port", "9011"])
        assert result.exit_code == 0, result.stdout
        assert os.environ["EXISTING"] == "keep"
        assert os.environ["SPACE"] == "trimmed"
        assert os.environ["HAS_EQUALS"] == "x=y"
        assert os.environ["SUPERVAIZER_HOST"] == "127.0.0.1"
        assert os.environ["SUPERVAIZER_PUBLIC_URL"] == "http://127.0.0.1:9011"

    mocked_file.assert_called_once_with(str(tmp_path / ".env"))
    launch.assert_called_once()
