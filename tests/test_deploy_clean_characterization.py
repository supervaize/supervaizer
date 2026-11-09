# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from collections.abc import Callable, Iterator
from io import StringIO
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

from supervaizer.deploy.commands.clean import (
    clean_deployment,
    clean_docker_artifacts,
    clean_state_only,
)

Cleanup = Callable[..., None]
DOCKER_FILES = {
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.yaml",
}
STATE_FILES = {"state.json", "config.yaml", "config.yml"}
OTHER_FILES = {"entrypoint.sh", "debug_env.py", "custom.txt", "nested/keep.txt"}
LOG_FILES = {"logs/deploy.log", "logs/nested/old.log"}
ALL_FILES = DOCKER_FILES | STATE_FILES | OTHER_FILES | LOG_FILES
COMMAND_CASES = [
    (
        clean_deployment,
        ALL_FILES,
        "\n[bold red]Are you sure you want to continue?[/]",
        "Deployment directory cleaned successfully",
    ),
    (
        clean_docker_artifacts,
        DOCKER_FILES | LOG_FILES,
        "\n[bold red]Continue with Docker cleanup?[/]",
        "Docker artifacts cleaned successfully",
    ),
    (
        clean_state_only,
        STATE_FILES,
        "\n[bold red]Continue with state cleanup?[/]",
        "Deployment state cleaned successfully",
    ),
]


@pytest.fixture
def cleanup_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    deployment_dir = tmp_path / ".deployment"
    for name in ALL_FILES:
        artifact = deployment_dir / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("dummy\n")
    return deployment_dir


@pytest.fixture
def cleanup_output(mocker: MockerFixture) -> StringIO:
    output = StringIO()
    mocker.patch(
        "supervaizer.deploy.commands.clean.console",
        Console(file=output, color_system=None, width=200),
    )
    return output


def remaining_files(deployment_dir: Path) -> set[str]:
    return {
        path.relative_to(deployment_dir).as_posix()
        for path in deployment_dir.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(("cleanup", "deleted", "prompt", "success"), COMMAND_CASES)
@pytest.mark.parametrize("verbose", [False, True])
def test_forced_cleanup_preserves_only_files_outside_its_scope(
    cleanup: Cleanup,
    deleted: set[str],
    prompt: str,
    success: str,
    verbose: bool,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    confirm = mocker.patch("supervaizer.deploy.commands.clean.Confirm.ask")

    cleanup(force=True, verbose=verbose)

    assert remaining_files(cleanup_tree) == ALL_FILES - deleted
    confirm.assert_not_called()
    output = cleanup_output.getvalue()
    assert success in output
    if cleanup is clean_docker_artifacts:
        assert "Deleted 5 items" in output
    elif cleanup is clean_state_only:
        assert "Deleted 3 state files" in output
    else:
        assert "Files deleted: 13" in output
    if verbose:
        assert "📄" in output
        assert "Deleting" in output
    else:
        assert "📄" not in output
    assert prompt.strip() not in output


@pytest.mark.parametrize(("cleanup", "deleted", "prompt", "success"), COMMAND_CASES)
@pytest.mark.parametrize("accepted", [False, True])
def test_cleanup_obeys_the_confirmation_response(
    cleanup: Cleanup,
    deleted: set[str],
    prompt: str,
    success: str,
    accepted: bool,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    confirm = mocker.patch(
        "supervaizer.deploy.commands.clean.Confirm.ask", return_value=accepted
    )

    cleanup()

    confirm.assert_called_once_with(prompt)
    expected = ALL_FILES - deleted if accepted else ALL_FILES
    assert remaining_files(cleanup_tree) == expected
    output = cleanup_output.getvalue()
    assert (success in output) is accepted
    assert ("Cleanup cancelled." in output) is not accepted


def test_verbose_full_cleanup_reports_size_and_nested_contents(
    tmp_path: Path,
    cleanup_output: StringIO,
) -> None:
    deployment_dir = tmp_path / "deployment"
    nested_dir = deployment_dir / "nested"
    nested_dir.mkdir(parents=True)
    (nested_dir / "large.log").write_bytes(b"x" * (1024 * 1024))
    (deployment_dir / "small.log").write_text("x")

    clean_deployment(deployment_dir, force=True, verbose=True)

    assert not deployment_dir.exists()
    output = cleanup_output.getvalue()
    assert "Contents to be deleted:" in output
    assert "📁 nested/" in output
    assert "📄 nested/large.log" in output
    assert "Summary: 2 files, 1.00 MB" in output
    assert "Files deleted: 2" in output
    assert "Space freed: 1.00 MB" in output
    assert "supervaizer deploy local" in output
    assert "supervaizer deploy up" in output
    assert "supervaizer deploy plan" in output


def partial_traversal(path: Path) -> Iterator[Path]:
    yield path
    raise PermissionError("dummy traversal denied")


def test_full_cleanup_uses_partial_counts_when_both_traversals_fail(
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    first_file = cleanup_tree / "Dockerfile"
    mocker.patch.object(
        Path,
        "rglob",
        side_effect=[partial_traversal(first_file), partial_traversal(first_file)],
    )

    clean_deployment(cleanup_tree, force=True, verbose=True)

    assert not cleanup_tree.exists()
    output = cleanup_output.getvalue()
    assert "📄 Dockerfile" in output
    assert "Summary: 1 files, 0.00 MB" in output
    assert "Files deleted: 1" in output
    assert "Deployment directory cleaned successfully" in output


def test_full_cleanup_omits_summary_when_size_traversal_fails_immediately(
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(Path, "rglob", side_effect=OSError("dummy listing failure"))

    clean_deployment(cleanup_tree, force=True)

    assert not cleanup_tree.exists()
    output = cleanup_output.getvalue()
    assert "Summary:" not in output
    assert "Files deleted:" not in output
    assert "Space freed:" not in output
    assert "Deployment directory cleaned successfully" in output


@pytest.mark.parametrize("error", [PermissionError("locked"), OSError("disk failure")])
def test_full_cleanup_wraps_deletion_errors_and_retains_the_directory(
    error: OSError,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    mocker.patch("supervaizer.deploy.commands.clean.shutil.rmtree", side_effect=error)

    with pytest.raises(
        RuntimeError, match=f"Failed to clean deployment directory: {error}"
    ) as caught:
        clean_deployment(cleanup_tree, force=True)

    assert caught.value.__cause__ is error
    assert remaining_files(cleanup_tree) == ALL_FILES
    output = cleanup_output.getvalue()
    assert f"Details: {error}" in output
    if isinstance(error, PermissionError):
        assert "Permission denied while deleting" in output
        assert "Make sure no processes are using files" in output
    else:
        assert "Error: Failed to clean deployment directory" in output
    assert "Cleanup completed!" not in output


@pytest.mark.parametrize(
    ("cleanup", "message"),
    [
        (clean_docker_artifacts, "Failed to clean Docker artifacts"),
        (clean_state_only, "Failed to clean deployment state"),
    ],
)
@pytest.mark.parametrize("error", [PermissionError("locked"), OSError("disk failure")])
def test_scoped_cleanup_wraps_unlink_errors_and_stops_deletion(
    cleanup: Cleanup,
    message: str,
    error: OSError,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    unlink = mocker.patch.object(Path, "unlink", side_effect=error)

    with pytest.raises(RuntimeError, match=f"{message}: {error}") as caught:
        cleanup(force=True, verbose=True)

    assert caught.value.__cause__ is error
    unlink.assert_called_once()
    assert remaining_files(cleanup_tree) == ALL_FILES
    assert f"Error: {message}" in cleanup_output.getvalue()
    assert f"Details: {error}" in cleanup_output.getvalue()


@pytest.mark.parametrize("error", [PermissionError("locked"), OSError("disk failure")])
def test_docker_cleanup_keeps_completed_file_deletions_when_log_deletion_fails(
    error: OSError,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    remove_tree = mocker.patch(
        "supervaizer.deploy.commands.clean.shutil.rmtree", side_effect=error
    )

    with pytest.raises(
        RuntimeError, match=f"Failed to clean Docker artifacts: {error}"
    ) as caught:
        clean_docker_artifacts(force=True, verbose=True)

    assert caught.value.__cause__ is error
    remove_tree.assert_called_once_with(Path(".deployment/logs"))
    assert remaining_files(cleanup_tree) == ALL_FILES - DOCKER_FILES
    output = cleanup_output.getvalue()
    assert "Deleting logs/..." in output
    assert "Docker artifacts cleaned successfully" not in output
    assert "Deleted 5 items" not in output


@pytest.mark.parametrize(
    ("cleanup", "first_file", "failing_file", "message"),
    [
        (
            clean_docker_artifacts,
            "Dockerfile",
            ".dockerignore",
            "Failed to clean Docker artifacts",
        ),
        (
            clean_state_only,
            "state.json",
            "config.yaml",
            "Failed to clean deployment state",
        ),
    ],
)
@pytest.mark.parametrize("error", [PermissionError("locked"), OSError("disk failure")])
def test_scoped_cleanup_retains_completed_deletions_when_the_next_unlink_fails(
    cleanup: Cleanup,
    first_file: str,
    failing_file: str,
    message: str,
    error: OSError,
    cleanup_tree: Path,
    cleanup_output: StringIO,
    mocker: MockerFixture,
) -> None:
    original_unlink = Path.unlink

    def unlink_until_failure(path: Path, missing_ok: bool = False) -> None:
        if path.name == failing_file:
            raise error
        original_unlink(path, missing_ok=missing_ok)

    unlink = mocker.patch.object(
        Path, "unlink", autospec=True, side_effect=unlink_until_failure
    )

    with pytest.raises(RuntimeError, match=f"{message}: {error}"):
        cleanup(force=True)

    assert unlink.call_count == 2
    assert remaining_files(cleanup_tree) == ALL_FILES - {first_file}
    assert "cleaned successfully" not in cleanup_output.getvalue()


def test_docker_cleanup_preserves_a_file_named_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_output: StringIO,
) -> None:
    monkeypatch.chdir(tmp_path)
    deployment_dir = tmp_path / ".deployment"
    deployment_dir.mkdir()
    (deployment_dir / "logs").write_text("dummy log")
    (deployment_dir / "Dockerfile").write_text("dummy image")

    clean_docker_artifacts(force=True, verbose=True)

    assert remaining_files(deployment_dir) == {"logs"}
    assert "Deleted 1 items" in cleanup_output.getvalue()
