# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Test for CLI module to improve coverage."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from supervaizer.cli import app


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

    def test_start_with_existing_script(
        self, runner: CliRunner, temp_script: str
    ) -> None:
        """Test start command with existing script."""
        with patch("builtins.exec") as mock_exec:
            # Try to run the command
            try:
                result = runner.invoke(app, ["start", temp_script])
                print(f"Result: {result}")
                print(f"Exit code: {result.exit_code}")
                print(f"Exception: {result.exception}")
                print(f"Output: {result.stdout}")
            except Exception as e:
                print(f"Exception caught: {e}")
                print(f"Exception type: {type(e)}")
                import traceback

                traceback.print_exc()
                raise

            assert result.exit_code == 0
            assert "Starting Supervaizer Controller" in result.stdout
            # The output contains ANSI color codes, so we need to check for the filename without the full path
            assert os.path.basename(temp_script) in result.stdout
            mock_exec.assert_called_once()

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
        assert "Create a draft supervaizer_control.py script" in str(result.stdout)


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
