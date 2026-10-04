# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Test for CLI module to improve coverage."""

import importlib.util
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from rich.console import Console
from typer.testing import CliRunner

from supervaizer.cli import app
from supervaizer.server import Server


@pytest.fixture(autouse=True)
def _cli_console_no_color(mocker: MockerFixture) -> None:
    """Rich marks up output unless Console is non-TTY; match plain-text assertions."""
    plain = Console(force_terminal=False, color_system=None, width=120)
    mocker.patch("supervaizer.cli.console", plain)


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_script() -> Generator[str, None, None]:
    """Create a temporary script file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('print("test script")')
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def mock_examples_dir() -> Generator[str, None, None]:
    """Mock the examples directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        examples_dir = Path(temp_dir)
        example_file = examples_dir / "a2a-controller.py"
        example_file.write_text("# Example controller")
        yield str(examples_dir)


class TestCLIStart:
    """Tests for the start command."""

    def test_start_with_missing_script(self, runner: CliRunner) -> None:
        """Test start command with missing script."""
        result = runner.invoke(app, ["start", "nonexistent.py"])

        assert result.exit_code == 1
        assert "Error: nonexistent.py not found" in result.stdout
        assert "Run supervaizer scaffold to create a default script" in result.stdout

    def test_start_with_default_script_missing(self, runner: CliRunner) -> None:
        """Test start command with default script missing."""
        result = runner.invoke(app, ["start"])

        assert result.exit_code == 1
        assert "Error: supervaizer_control.py not found" in result.stdout

    def test_start_local_sets_env_and_runs_script(
        self, runner: CliRunner, temp_script: str
    ) -> None:
        """--local sets SUPERVAIZER_LOCAL_MODE and imports the script, finds Server, calls launch()."""
        with patch("supervaizer.server.Server.launch") as mock_launch:
            # Write a real control script that creates a Server instance
            with open(temp_script, "w") as f:
                f.write(
                    "from supervaizer.server import Server\n"
                    "from supervaizer.examples.local_server import get_default_local_agent\n"
                    "sv_server = Server(agents=[get_default_local_agent()])\n"
                )
            result = runner.invoke(app, ["start", "--local", temp_script])
            assert "local test mode" in result.stdout
            assert os.environ.get("SUPERVAIZER_LOCAL_MODE") == "true"
            mock_launch.assert_called_once()

    def test_start_local_without_script_uses_fallback(self, runner: CliRunner) -> None:
        """--local without script_path and no supervaizer_control.py uses built-in fallback."""
        with (
            patch("supervaizer.server.Server.launch") as mock_launch,
            patch("supervaizer.cli.os.path.exists", return_value=False),
        ):
            result = runner.invoke(app, ["start", "--local"])
            assert "local test mode" in result.stdout
            assert "built-in Hello World agent" in result.stdout
            mock_launch.assert_called_once()

    @pytest.mark.parametrize(
        ("flag", "debug"), [("--debug", True), ("--reload", False)]
    )
    def test_start_accepts_deprecated_flags(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        flag: str,
        debug: bool,
    ) -> None:
        """--debug and --reload still run, with a deprecation warning."""
        monkeypatch.setenv("SUPERVAIZER_DEBUG", "false")
        monkeypatch.setenv("SUPERVAIZER_RELOAD", "false")
        with (
            patch.object(Server, "launch", autospec=True) as mock_launch,
            patch("supervaizer.cli.os.path.exists", return_value=False),
        ):
            result = runner.invoke(app, ["start", "--local", flag])

        assert result.exit_code == 0
        assert f"{flag} is deprecated" in result.stdout
        server = mock_launch.call_args.args[0]
        assert server.debug is debug
        # Uvicorn rejects reload=True with an app object, so the fallback ignores it.
        assert server.reload is False
        assert os.environ[f"SUPERVAIZER_{flag[2:].upper()}"] == "True"


class TestCLIScaffoldInstructions:
    """Tests for the scaffold instructions subcommand."""

    def test_existing_file_hint_names_scaffold_subcommand(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """The overwrite hint names the real `scaffold refresh-instructions` command."""
        instructions = tmp_path / "supervaize_instructions.html"
        instructions.write_text("<p>custom</p>")

        result = runner.invoke(
            app,
            [
                "scaffold",
                "instructions",
                "--control-file",
                str(tmp_path / "supervaizer_control.py"),
            ],
        )

        assert "supervaizer scaffold refresh-instructions" in result.stdout
        assert instructions.read_text() == "<p>custom</p>"


class TestCLIInstall:
    """Tests for the scaffold command."""

    def test_scaffold_success(self, runner: CliRunner) -> None:
        """Test successful scaffold command."""
        with (
            patch("os.path.exists", return_value=False),
            patch("supervaizer.cli.Path") as mock_path_class,
            patch("shutil.copy") as mock_copy,
        ):
            # Create a proper mock for the Path object chain
            mock_examples_dir = Mock()
            mock_example_file = Mock()
            mock_example_file.exists.return_value = True

            # Mock the chain: Path(__file__).parent / "examples" / "a2a-controller.py"
            mock_file_path = Mock()
            mock_parent1 = Mock()

            mock_path_class.return_value = mock_file_path
            mock_file_path.parent = mock_parent1
            mock_parent1.__truediv__ = Mock(return_value=mock_examples_dir)
            mock_examples_dir.__truediv__ = Mock(return_value=mock_example_file)

            result = runner.invoke(app, ["scaffold"])

            assert result.exit_code == 0
            assert (
                "Success: Created an example file at supervaizer_control.py"
                in result.stdout
            )
            assert "Copy this file to" in result.stdout
            mock_copy.assert_called_once()

    def test_scaffold_file_exists_without_force(self, runner: CliRunner) -> None:
        """Test scaffold when file exists without force flag."""
        with patch("os.path.exists", return_value=True):
            result = runner.invoke(app, ["scaffold"])

            assert result.exit_code == 1
            assert "Error: supervaizer_control.py already exists" in result.stdout
            assert "Use --force to overwrite it" in result.stdout

    def test_scaffold_with_force(self, runner: CliRunner) -> None:
        """Test scaffold with force flag."""
        with (
            patch("os.path.exists", return_value=True),
            patch("supervaizer.cli.Path") as mock_path_class,
            patch("shutil.copy") as mock_copy,
            patch(
                "supervaizer.cli._create_instructions_file"
            ) as mock_create_instructions,
        ):
            # Create proper mock chain
            mock_examples_dir = Mock()
            mock_example_file = Mock()
            mock_example_file.exists.return_value = True

            mock_file_path = Mock()
            mock_parent1 = Mock()

            mock_path_class.return_value = mock_file_path
            mock_file_path.parent = mock_parent1
            mock_parent1.__truediv__ = Mock(return_value=mock_examples_dir)
            mock_examples_dir.__truediv__ = Mock(return_value=mock_example_file)

            # Mock the instructions file creation
            mock_instructions_path = Mock()
            mock_create_instructions.return_value = mock_instructions_path

            result = runner.invoke(app, ["scaffold", "--force"])

            assert result.exit_code == 0
            assert (
                "Success: Created an example file at supervaizer_control.py"
                in result.stdout
            )
            mock_copy.assert_called_once()

    def test_scaffold_custom_output_path(self, runner: CliRunner) -> None:
        """Test scaffold with custom output path."""
        custom_path = "custom_controller.py"

        with (
            patch("os.path.exists", return_value=False),
            patch("supervaizer.cli.Path") as mock_path_class,
            patch("shutil.copy") as _mock_copy,
        ):
            # Create proper mock chain
            mock_examples_dir = Mock()
            mock_example_file = Mock()
            mock_example_file.exists.return_value = True

            mock_file_path = Mock()
            mock_parent1 = Mock()

            mock_path_class.return_value = mock_file_path
            mock_file_path.parent = mock_parent1
            mock_parent1.__truediv__ = Mock(return_value=mock_examples_dir)
            mock_examples_dir.__truediv__ = Mock(return_value=mock_example_file)

            result = runner.invoke(app, ["scaffold", "--output-path", custom_path])

            assert result.exit_code == 0
            assert f"Success: Created an example file at {custom_path}" in result.stdout

    def test_scaffold_template_is_a_working_v2_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The scaffolded control file serves its v2 surface and action in local mode."""
        monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
        monkeypatch.setenv("SUPERVAIZER_API_KEY", "local-dev")
        template = (
            Path(__file__).parent.parent
            / "src/supervaizer/examples/controller_template.py"
        )
        spec = importlib.util.spec_from_file_location("scaffolded_control", template)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client = TestClient(module.sv_server.app)
        params = {
            "request_id": "r1",
            "actor": {"user_id": "me"},
            "workspace": {"id": "local"},
            "mission_id": "m1",
            "agent_slug": module.agent.slug,
            "surface": "job.start",
        }

        def call(method: str, **extra: Any) -> dict[str, Any]:
            response = client.post(
                "/a2a",
                headers={"X-API-Key": "local-dev"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": {**params, **extra},
                },
            )
            result: dict[str, Any] = response.json()["result"]
            return result

        surface = call("supervaizer/surface.load")
        assert surface["document"]["submit"]["action"] == "job.start"

        started = call(
            "supervaizer/action.invoke",
            action="job.start",
            input={"goal": "Say hello"},
            job_id="job-1",
        )
        assert started["status"] == "ok"
        assert started["job_state"]["cases"][0]["title"] == "Say hello"

    def test_scaffold_example_file_not_found(self, runner: CliRunner) -> None:
        """Test scaffold when example file doesn't exist."""
        with (
            patch("os.path.exists", return_value=False),
            patch("supervaizer.cli.Path") as mock_path_class,
        ):
            # Create proper mock chain with non-existent example file
            mock_examples_dir = Mock()
            mock_example_file = Mock()
            mock_example_file.exists.return_value = False

            mock_file_path = Mock()
            mock_parent1 = Mock()

            mock_path_class.return_value = mock_file_path
            mock_file_path.parent = mock_parent1
            mock_parent1.__truediv__ = Mock(return_value=mock_examples_dir)
            mock_examples_dir.__truediv__ = Mock(return_value=mock_example_file)

            result = runner.invoke(app, ["scaffold"])

            assert result.exit_code == 1
            assert "Error: Example file not found" in result.stdout

    def test_scaffold_uses_environment_defaults(self, runner: CliRunner) -> None:
        """Test that scaffold command properly handles output path and force options."""
        with (
            patch("os.path.exists", return_value=False),
            patch("supervaizer.cli.Path") as mock_path_class,
            patch("shutil.copy") as mock_copy,
        ):
            # Create proper mock chain
            mock_examples_dir = Mock()
            mock_example_file = Mock()
            mock_example_file.exists.return_value = True

            mock_file_path = Mock()
            mock_parent1 = Mock()

            mock_path_class.return_value = mock_file_path
            mock_file_path.parent = mock_parent1
            mock_parent1.__truediv__ = Mock(return_value=mock_examples_dir)
            mock_examples_dir.__truediv__ = Mock(return_value=mock_example_file)

            # Test with custom output path
            result = runner.invoke(
                app, ["scaffold", "--output-path", "custom_script.py"]
            )

            assert result.exit_code == 0
            assert (
                "Success: Created an example file at custom_script.py" in result.stdout
            )
            mock_copy.assert_called_once()


class TestCLIApp:
    """Tests for the CLI app itself."""

    def test_app_help(self, runner: CliRunner) -> None:
        """Test CLI app help output."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Supervaizer Controller CLI" in result.stdout
        assert "start" in result.stdout
        assert "scaffold" in result.stdout

    def test_start_command_help(self, runner: CliRunner) -> None:
        """Test start command help."""
        result = runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        assert "Start the Supervaizer Controller server" in str(result.stdout)

    def test_scaffold_command_help(self, runner: CliRunner) -> None:
        """Test scaffold command help."""
        result = runner.invoke(app, ["scaffold", "--help"])

        assert result.exit_code == 0
        assert "Scaffold commands for creating project files" in str(result.stdout)


@patch("supervaizer.cli.app")
def test_main_execution(mock_app: Mock) -> None:
    """Test main execution when module is run directly."""
    # Import the module to trigger the if __name__ == "__main__" block
    import importlib

    import supervaizer.cli

    # Reload to trigger main execution
    with patch("sys.argv", ["cli.py"]):
        importlib.reload(supervaizer.cli)

    # Note: We can't easily test the actual execution due to typer's nature,
    # but we can verify the structure is correct
