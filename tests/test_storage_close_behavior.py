# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Pin shutdown behavior without closing the shared test database."""

import pytest
from pytest_mock import MockerFixture

from supervaizer.storage import StorageManager


def test_close_closes_the_database_once(
    storage_manager: StorageManager, mocker: MockerFixture
) -> None:
    database = mocker.Mock()
    mocker.patch.object(storage_manager, "_db", database)

    storage_manager.close()

    database.close.assert_called_once_with()


def test_close_accepts_a_database_that_is_already_closed(
    storage_manager: StorageManager, mocker: MockerFixture
) -> None:
    database = mocker.Mock()
    database.close.side_effect = ValueError("I/O operation on closed file.")
    mocker.patch.object(storage_manager, "_db", database)

    storage_manager.close()

    database.close.assert_called_once_with()


def test_close_preserves_unexpected_database_errors(
    storage_manager: StorageManager, mocker: MockerFixture
) -> None:
    error = ValueError("broken database")
    database = mocker.Mock()
    database.close.side_effect = error
    mocker.patch.object(storage_manager, "_db", database)

    with pytest.raises(ValueError, match="broken database") as caught:
        storage_manager.close()

    assert caught.value is error
