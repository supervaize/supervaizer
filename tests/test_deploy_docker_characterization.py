# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, call

import pytest
from docker.errors import APIError, BuildError, DockerException, ImageNotFound
from pytest_mock import MockerFixture

from supervaizer.deploy.docker import DockerManager


@pytest.fixture
def build_manager(mocker: MockerFixture) -> tuple[DockerManager, Mock]:
    manager = DockerManager(require_docker=False)
    client = mocker.Mock()
    manager.client = client
    client.images.get.return_value.id = "sha256:lookup"
    return manager, client


@pytest.fixture
def build_log(mocker: MockerFixture) -> Mock:
    return mocker.patch("supervaizer.deploy.docker.log")


@pytest.mark.parametrize("verbose", [False, True])
def test_build_forwards_explicit_paths_tag_arguments_and_cleanup_flags(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    verbose: bool,
) -> None:
    manager, client = build_manager
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    dockerfile = tmp_path / "generated" / "Dockerfile"
    dockerfile.parent.mkdir()
    dockerfile.write_text("FROM scratch\n")
    build_args = {"PYTHON_VERSION": "3.12"}
    client.api.build.return_value = iter([
        {"stream": "step one\n"},
        {"aux": {"ID": "sha256:built"}},
    ])

    result = manager.build_image(
        "dummy-app:release", source_dir, dockerfile, verbose, build_args
    )

    assert result == "sha256:built"
    client.api.build.assert_called_once_with(
        path=str(source_dir),
        dockerfile=str(dockerfile),
        tag="dummy-app:release",
        rm=True,
        forcerm=True,
        buildargs=build_args,
        decode=True,
    )
    assert client.api.build.call_args.kwargs["buildargs"] is build_args
    client.images.get.assert_not_called()
    assert capsys.readouterr().out == "step one\n"
    assert dockerfile.read_text() == "FROM scratch\n"
    assert source_dir.is_dir()
    assert client.close.call_count == 0
    assert build_log.info.call_args_list == [
        call("Building Docker image with tag: dummy-app:release"),
        call("Successfully built image: sha256:built"),
    ]


def test_build_uses_default_paths_and_falls_back_to_the_exact_tag(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter([{"stream": ""}])

    assert manager.build_image("dummy-app:latest") == "sha256:lookup"

    client.api.build.assert_called_once_with(
        path=".",
        dockerfile=".deployment/Dockerfile",
        tag="dummy-app:latest",
        rm=True,
        forcerm=True,
        buildargs={},
        decode=True,
    )
    client.images.get.assert_called_once_with("dummy-app:latest")


def test_build_prints_all_string_fields_in_order_and_ignores_other_records(
    build_manager: tuple[DockerManager, Mock],
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    manager, client = build_manager
    print_output = mocker.patch("builtins.print", wraps=print)
    client.api.build.return_value = iter([
        "ignored record",
        None,
        123,
        {"stream": "first", "status": "second", "progress": 4, "extra": ["skip"]},
        {"aux": "printed auxiliary text"},
        {"aux": {"ID": "sha256:built"}, "stream": "last\n"},
    ])

    assert manager.build_image("dummy:tag") == "sha256:built"

    assert capsys.readouterr().out == "firstsecondprinted auxiliary textlast\n"
    assert print_output.call_args_list == [
        call("first", end="", flush=True),
        call("second", end="", flush=True),
        call("printed auxiliary text", end="", flush=True),
        call("last\n", end="", flush=True),
    ]


@pytest.mark.parametrize(
    ("records", "expected", "lookup"),
    [
        (
            [{"aux": {"ID": "sha256:first"}}, {"aux": {"ID": "sha256:last"}}],
            "sha256:last",
            False,
        ),
        ([{"aux": {"ID": "sha256:first"}}, {"aux": {}}], "sha256:lookup", True),
        ([{"aux": {"ID": ""}}], "", False),
        ([{"aux": {"ID": None}}], "sha256:lookup", True),
        ([{"aux": None}], "sha256:lookup", True),
    ],
)
def test_build_uses_the_last_auxiliary_id_and_looks_up_only_none(
    build_manager: tuple[DockerManager, Mock],
    records: list[dict[str, object]],
    expected: str,
    lookup: bool,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter(records)

    assert manager.build_image("dummy:tag") == expected

    assert client.images.get.called is lookup


@pytest.mark.parametrize(
    ("records", "message", "stdout"),
    [
        ([{"error": "first"}, {"errorDetail": {"message": "last"}}], "last", "first"),
        (
            [{"error": "preferred", "errorDetail": {"message": "ignored"}}],
            "preferred",
            "preferred",
        ),
        ([{"error": "", "errorDetail": {"message": "detail"}}], "detail", ""),
        ([{"errorDetail": {}}], "Unknown error", ""),
        ([{"error": ""}], "Unknown error", ""),
    ],
)
def test_build_raises_the_last_error_after_printing_the_full_stream(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
    capsys: pytest.CaptureFixture[str],
    records: list[dict[str, object]],
    message: str,
    stdout: str,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter([
        *records,
        {"aux": {"ID": "sha256:built"}},
        {"stream": "after error\n"},
    ])

    with pytest.raises(
        RuntimeError, match=f"^Docker build failed: {message}$"
    ) as caught:
        manager.build_image("dummy:tag")

    assert caught.value.__cause__ is None
    assert capsys.readouterr().out == stdout + "after error\n"
    client.images.get.assert_not_called()
    build_log.error.assert_not_called()


@pytest.mark.parametrize("last_message", ["", None])
def test_build_accepts_a_falsy_last_error_message_after_an_earlier_error(
    build_manager: tuple[DockerManager, Mock],
    last_message: str | None,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter([
        {"error": "earlier failure"},
        {"errorDetail": {"message": last_message}},
        {"aux": {"ID": "sha256:built"}},
    ])

    assert manager.build_image("dummy:tag") == "sha256:built"


def test_build_rejects_an_empty_stream_without_image_lookup(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter([])

    with pytest.raises(
        RuntimeError, match="^Failed to get a response from docker client$"
    ):
        manager.build_image("dummy:tag")

    client.images.get.assert_not_called()
    build_log.error.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        BuildError("dummy SDK failure", build_log=[]),
        APIError("dummy SDK failure"),
        DockerException("dummy SDK failure"),
    ],
)
@pytest.mark.parametrize("during_iteration", [False, True])
def test_build_wraps_sdk_errors_with_the_original_cause(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
    capsys: pytest.CaptureFixture[str],
    error: DockerException,
    during_iteration: bool,
) -> None:
    manager, client = build_manager

    def failing_stream() -> Iterator[dict[str, str]]:
        yield {"stream": "not printed before iteration completes"}
        raise error

    if during_iteration:
        client.api.build.return_value = failing_stream()
    else:
        client.api.build.side_effect = error

    with pytest.raises(
        RuntimeError, match="^Docker build failed: dummy SDK failure$"
    ) as caught:
        manager.build_image("dummy:tag")

    assert caught.value.__cause__ is error
    assert capsys.readouterr().out == ""
    client.images.get.assert_not_called()
    build_log.error.assert_called_once_with(
        "Failed to build Docker image: dummy SDK failure"
    )


@pytest.mark.parametrize(
    "error", [ImageNotFound("missing"), DockerException("missing")]
)
def test_build_image_lookup_failure_keeps_its_context_without_an_explicit_cause(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
    error: DockerException,
) -> None:
    manager, client = build_manager
    client.api.build.return_value = iter([{"stream": ""}])
    client.images.get.side_effect = error

    with pytest.raises(
        RuntimeError, match="^Docker build completed but no image was returned$"
    ) as caught:
        manager.build_image("dummy:tag")

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is error
    client.images.get.assert_called_once_with("dummy:tag")
    build_log.error.assert_not_called()


def test_build_propagates_non_sdk_iteration_errors_without_partial_output(
    build_manager: tuple[DockerManager, Mock],
    build_log: Mock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manager, client = build_manager
    error = ValueError("dummy invalid stream")

    def failing_stream() -> Iterator[dict[str, str]]:
        yield {"stream": "not printed before iteration completes"}
        raise error

    client.api.build.return_value = failing_stream()

    with pytest.raises(ValueError, match="dummy invalid stream") as caught:
        manager.build_image("dummy:tag")

    assert caught.value is error
    assert capsys.readouterr().out == ""
    client.images.get.assert_not_called()
    build_log.error.assert_not_called()


def test_build_without_a_client_fails_before_any_build_logging(build_log: Mock) -> None:
    manager = DockerManager(require_docker=False)

    with pytest.raises(RuntimeError, match="^Docker client not available\\."):
        manager.build_image("dummy:tag")

    build_log.info.assert_not_called()
